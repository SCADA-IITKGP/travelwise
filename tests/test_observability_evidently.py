from fastapi.testclient import TestClient

from backend import evidently_monitor, main, store


def test_observability_pipeline_endpoint():
    client = TestClient(main.app)

    resp = client.get("/api/v1/observability/pipeline")
    assert resp.status_code == 200
    body = resp.json()
    assert [lvl["level"] for lvl in body["levels"]] == [1, 2, 3, 4]
    assert "curl_commands" not in body


def test_pipeline_diagnostic_returns_all_four_levels():
    client = TestClient(main.app)
    resp = client.post(
        "/api/v1/observability/pipeline/test",
        json={"query": "What receipts are required for expense reimbursement?", "organization_id": "globaltech"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["levels"]) == 4
    assert data["levels"][0]["status"] == "passed"
    assert data["levels"][1]["documents_found"] > 0
    assert "critic" in data["levels"][2]
    assert "answer" in data["levels"][3]


def test_evidently_report_generation_and_ui_endpoints(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DATABASE_PATH", str(tmp_path / "obs.db"))
    store.init_db()
    monkeypatch.setattr(evidently_monitor, "RESULTS_DIR", tmp_path)

    client = TestClient(main.app)
    run_resp = client.post("/api/v1/observability/evidently/run?source=evaluation")
    assert run_resp.status_code == 200
    summary = run_resp.json()
    assert summary["source"] == "evaluation"
    assert summary["row_count"] >= 1
    assert summary["metrics_count"] > 0
    assert summary["report_url"] == "/api/v1/observability/evidently/report?source=evaluation"

    html_resp = client.get("/api/v1/observability/evidently/report?source=evaluation")
    assert html_resp.status_code == 200
    assert "text/html" in html_resp.headers["content-type"]
    assert "<html" in html_resp.text.lower()

    traces_resp = client.post("/api/v1/observability/evidently/run?source=traces")
    assert traces_resp.status_code == 200
    assert traces_resp.json()["source"] == "traces"
