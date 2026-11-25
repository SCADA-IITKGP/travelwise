import asyncio
from pathlib import Path
from fastapi.testclient import TestClient

from backend import embeddings, llm, main, rag


def test_llm_models_and_selection_validation(monkeypatch, tmp_path):
    cert = tmp_path / "vm04-ca.crt"
    cert.write_text("dummy", encoding="utf-8")

    monkeypatch.setattr(llm, "_mode", "mock")
    monkeypatch.setattr(llm, "_api_key", "")
    monkeypatch.setattr(llm, "_ca_cert_file", "")
    monkeypatch.setattr(llm, "_model", "Qwen/Qwen3-8B")
    monkeypatch.setattr(llm, "_base_url", "https://103.42.50.41:1034/v1")
    monkeypatch.setattr(llm.ssl, "create_default_context", lambda cafile=None: None)
    monkeypatch.setattr(main.store, "save_trace", lambda trace: None)

    client = TestClient(main.app)

    models_resp = client.get("/api/v1/llm/models")
    assert models_resp.status_code == 200
    body = models_resp.json()
    assert body["active_selection"] == "evidence-only"
    assert any(m["id"] == "Qwen/Qwen3-8B" for m in body["models"])

    fail_resp = client.post("/api/v1/llm/select", json={"selection": "Qwen/Qwen3-8B", "mode": "hosted"})
    assert fail_resp.status_code == 422

    ok_resp = client.post(
        "/api/v1/llm/select",
        json={
            "selection": "Qwen/Qwen3-8B",
            "mode": "hosted",
            "model": "Qwen/Qwen3-8B",
            "base_url": "https://103.42.50.41:1034/v1",
            "api_key": "test-group-key",
            "ca_cert_file": str(cert),
        },
    )
    assert ok_resp.status_code == 200
    assert ok_resp.json()["active_selection"] == "Qwen/Qwen3-8B"
    assert ok_resp.json()["mode"] == "hosted"

    back_resp = client.post("/api/v1/llm/select", json={"selection": "evidence-only", "mode": "mock"})
    assert back_resp.status_code == 200
    assert back_resp.json()["active_selection"] == "evidence-only"


def test_embeddings_batching_and_rag_integration(monkeypatch, tmp_path):
    cert = tmp_path / "vm02-ca.crt"
    cert.write_text("dummy", encoding="utf-8")

    monkeypatch.setattr(embeddings, "_mode", "hybrid")
    monkeypatch.setattr(embeddings, "_base_url", "https://103.42.50.41:1035/v1")
    monkeypatch.setattr(embeddings, "_api_key", "test-emb-key")
    monkeypatch.setattr(embeddings, "_model", "bge-small-en-v1.5")
    monkeypatch.setattr(embeddings, "_ca_cert_file", str(cert))
    monkeypatch.setattr(embeddings.ssl, "create_default_context", lambda cafile=None: None)

    batch_sizes = []

    class FakeResp:
        def __init__(self, count):
            self.status_code = 200
            self._count = count

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {"index": i, "embedding": [1.0 if i == 0 else 0.1] + [0.0] * 383}
                    for i in range(self._count)
                ]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, headers=None, json=None):
            assert url == "https://103.42.50.41:1035/v1/embeddings"
            assert json["model"] == "bge-small-en-v1.5"
            batch_sizes.append(len(json["input"]))
            return FakeResp(len(json["input"]))

    monkeypatch.setattr(embeddings.httpx, "Client", FakeClient)

    vectors = embeddings.embed_texts([f"chunk {i}" for i in range(20)])
    assert len(vectors) == 20
    assert len(vectors[0]) == 384
    assert batch_sizes == [16, 4]


def test_rag_falls_back_cleanly_when_embedding_endpoint_errors(monkeypatch):
    monkeypatch.setattr(rag.embeddings, "is_configured", lambda: True)

    def fail_embed(texts):
        raise embeddings.EmbeddingError("Capacity limit")

    monkeypatch.setattr(rag.embeddings, "embed_texts", fail_embed)
    rag._embedding_cache.clear()
    docs = rag.retrieve("lost receipt declaration", organization_id="globaltech")
    assert len(docs) > 0
