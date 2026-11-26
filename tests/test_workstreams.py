import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from backend import llm, main, market_data, rag, store
from backend.agents import run_agent
from evaluation.run_evaluation import compare_prompt_strategies


def test_prompt_strategy_comparison_covers_all_variants():
    comparison = compare_prompt_strategies()
    assert set(comparison.keys()) == {"v1_baseline", "v2_grounded", "v3_structured_critic"}
    assert comparison["v1_baseline"]["passed_all"] is False
    assert comparison["v2_grounded"]["passed_all"] is True
    assert comparison["v3_structured_critic"]["passed_all"] is True
    assert comparison["v3_structured_critic"]["structured_json_output"] is True


def test_structured_output_and_critic_repair_loop(monkeypatch):
    calls = []

    def fake_policy_search(query, grade, organization_id="default"):
        return {
            "documents": [{"id": "GT-TRV-EXP-025#clause-1", "document_id": "GT-TRV-EXP-025", "text": "Splitting transactions is prohibited."}],
            "citations": ["GT-TRV-EXP-025#clause-1"],
        }

    async def fake_generate(system_prompt, user_prompt, model_override=None):
        calls.append(user_prompt)
        if len(calls) == 1:
            return '{"answer": "No splitting allowed [FAKE-DOC-999].", "citations": ["FAKE-DOC-999"], "missing_inputs": [], "recommended_action": "refuse", "requires_human_approval": false}'
        return '{"answer": "No, splitting transactions is prohibited [GT-TRV-EXP-025].", "citations": ["GT-TRV-EXP-025"], "missing_inputs": [], "recommended_action": "refuse", "requires_human_approval": false}'

    from backend import agents

    monkeypatch.setattr(agents.tools, "policy_search", fake_policy_search)
    monkeypatch.setattr(agents, "generate", fake_generate)
    monkeypatch.setattr(agents, "current_mode", lambda: "hosted")

    trace = asyncio.run(run_agent("Can I split a hotel bill?", "EMP1"))

    assert len(calls) == 2
    assert trace["structured_output_valid"] is True
    assert trace["structured_output"]["recommended_action"] == "refuse"
    assert trace["structured_output"]["citations"] == ["GT-TRV-EXP-025"]
    assert trace["critic"]["passed"] is True
    assert [s["tool"] for s in trace["steps_log"]] == ["receipt_extract", "policy_search", "expense_validate", "critic", "critic_repair"]


def test_session_memory_persists_across_turns_and_redacts_pii(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DATABASE_PATH", str(tmp_path / "mem.db"))
    store.init_db()

    from backend import agents

    prompts = []

    def fake_policy_search(query, grade, organization_id="default"):
        return {
            "documents": [{"id": "GT-TRV-EXP-002#clause-1", "document_id": "GT-TRV-EXP-002", "text": "Receipts are required."}],
            "citations": ["GT-TRV-EXP-002#clause-1"],
        }

    async def fake_generate(system_prompt, user_prompt, model_override=None):
        prompts.append(user_prompt)
        return "Itemised receipts are required [GT-TRV-EXP-002]."

    monkeypatch.setattr(agents.tools, "policy_search", fake_policy_search)
    monkeypatch.setattr(agents, "generate", fake_generate)

    t1 = asyncio.run(run_agent("My email is alice@example.com. What receipts do I need?", "EMP1", session_id="SES-TEST"))
    assert "[REDACTED_EMAIL]" in t1["query"]

    t2 = asyncio.run(run_agent("And for meals?", "EMP1", session_id="SES-TEST"))
    assert t2["status"] == "success"
    assert "Conversation history:" in prompts[1]
    assert "[REDACTED_EMAIL]" in prompts[1]
    assert "alice@example.com" not in prompts[1]


def test_rag_reranking_demotes_historical_when_not_asked():
    candidates = [
        (0.80, {"id": "GT-TRV-AMD-017#clause-1", "document_id": "GT-TRV-AMD-017", "title": "Historical hotel allowance schedule", "search_text": "Archived illustrative schedule hotel allowance", "text": "Archived schedule"}),
        (0.76, {"id": "GT-TRV-EXP-001#clause-1", "document_id": "GT-TRV-EXP-001", "title": "Expense eligibility taxonomy", "search_text": "Current hotel eligibility rules", "text": "Current hotel rules"}),
    ]
    reranked = rag._rerank("What hotel expenses can be claimed?", candidates, top_k=2)
    assert reranked[0]["document_id"] == "GT-TRV-EXP-001"


def test_fx_caching_and_deployment_manifests_present(monkeypatch):
    market_data._cache.clear()
    market_data._counters = {"requests": 0, "fresh_cache_hits": 0, "stale_fallbacks": 0, "provider_errors": 0}
    market_data._cache[("USD", "INR")] = {
        "base": "USD",
        "quote": "INR",
        "rate": 84.5,
        "rate_date": "2026-11-25",
        "retrieved_at": "2026-11-25T00:00:00+00:00",
        "cached_monotonic": 10**12,
    }
    res = asyncio.run(market_data.get_rate("USD", "INR"))
    assert res["freshness"] == "cached"
    assert market_data.status()["fresh_cache_hits"] == 1

    root = Path(__file__).resolve().parents[1]
    for rel in (
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.hosted.yml",
        "deployment/Dockerfile.backend",
        "deployment/Dockerfile.frontend",
        "deployment/k8s.yaml",
        "deployment/openshift-route.yaml",
        "docs/DOMAIN_SPEC.md",
    ):
        assert (root / rel).is_file(), f"Missing {rel}"

    client = TestClient(main.app)
    health = client.get("/health")
    assert health.status_code == 200
    assert "rag_cache" in health.json()
    assert "X-RateLimit-Limit" in client.get("/api/v1/llm/status").headers
