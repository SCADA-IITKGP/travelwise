import asyncio
from fastapi.testclient import TestClient

from backend import agents, main


def test_direct_question_does_not_check_or_attach_context(monkeypatch):
    captured = {}

    def fake_policy_search(query, grade, organization_id="default"):
        captured["search_query"] = query
        captured["search_grade"] = grade
        return {
            "documents": [{"id": "POL-MEAL-GENERAL", "text": "Meal reimbursement requires an itemized receipt."}],
            "citations": ["POL-MEAL-GENERAL"],
        }

    async def fake_generate(system_prompt, user_prompt, model_override=None):
        captured["user_prompt"] = user_prompt
        captured["model_override"] = model_override
        return "Itemized receipts are required for meal reimbursement [POL-MEAL-GENERAL]."

    monkeypatch.setattr(agents.tools, "policy_search", fake_policy_search)
    monkeypatch.setattr(agents, "generate", fake_generate)

    trace = asyncio.run(agents.run_agent("What is the meal policy?", "EMP1001"))

    assert trace["status"] == "success"
    assert "travel_context" not in trace
    assert captured["search_query"] == "What is the meal policy?"
    assert captured["search_grade"] == "ALL"
    assert "Selected travel context" not in captured["user_prompt"]
    assert "not provided" not in captured["user_prompt"]


def test_selected_context_is_used_in_search_and_answer_prompt(monkeypatch):
    captured = {}

    def fake_policy_search(query, grade, organization_id="default"):
        captured["search_query"] = query
        captured["search_grade"] = grade
        return {
            "documents": [{"id": "POL-JP-HOTEL", "text": "Grade G3 international hotel allowance in Japan."}],
            "citations": ["POL-JP-HOTEL"],
        }

    async def fake_generate(system_prompt, user_prompt, model_override=None):
        captured["user_prompt"] = user_prompt
        captured["model_override"] = model_override
        return "For G3 international travel to Japan, follow [POL-JP-HOTEL]."

    monkeypatch.setattr(agents.tools, "policy_search", fake_policy_search)
    monkeypatch.setattr(agents, "generate", fake_generate)

    trace = asyncio.run(
        agents.run_agent(
            "What is the hotel limit?",
            "EMP1001",
            grade="G3",
            travel_context={
                "destination_country": "Japan",
                "employee_grade": "G3",
                "trip_type": "International",
            },
        )
    )

    assert trace["status"] == "success"
    assert trace["travel_context"] == {
        "destination_country": "Japan",
        "employee_grade": "G3",
        "trip_type": "International",
    }
    assert captured["search_query"] == "What is the hotel limit? Japan G3 International"
    assert captured["search_grade"] == "G3"
    assert "Selected travel context:" in captured["user_prompt"]
    assert "- Destination country: Japan" in captured["user_prompt"]
    assert "- Employee grade: G3" in captured["user_prompt"]
    assert "- Trip type: International" in captured["user_prompt"]


def test_partial_context_omits_blank_fields(monkeypatch):
    captured = {}

    def fake_policy_search(query, grade, organization_id="default"):
        captured["search_query"] = query
        captured["search_grade"] = grade
        return {
            "documents": [{"id": "POL-JP-001", "text": "Japan travel policy."}],
            "citations": ["POL-JP-001"],
        }

    async def fake_generate(system_prompt, user_prompt, model_override=None):
        captured["user_prompt"] = user_prompt
        captured["model_override"] = model_override
        return "Follow [POL-JP-001]."

    monkeypatch.setattr(agents.tools, "policy_search", fake_policy_search)
    monkeypatch.setattr(agents, "generate", fake_generate)

    trace = asyncio.run(
        agents.run_agent(
            "Do I need pre-approval?",
            "EMP1001",
            travel_context={"destination_country": "Japan", "employee_grade": "", "trip_type": None},
        )
    )

    assert trace["travel_context"] == {"destination_country": "Japan"}
    assert captured["search_query"] == "Do I need pre-approval? Japan"
    assert captured["search_grade"] == "ALL"
    assert "- Destination country: Japan" in captured["user_prompt"]
    assert "Employee grade:" not in captured["user_prompt"]
    assert "Trip type:" not in captured["user_prompt"]


def test_chat_endpoint_accepts_direct_and_contextual_requests(monkeypatch):
    async def fake_generate(system_prompt, user_prompt, model_override=None):
        return "Mock response"

    monkeypatch.setattr(agents, "generate", fake_generate)
    monkeypatch.setattr(
        agents.tools,
        "policy_search",
        lambda q, g, organization_id="default": {"documents": [{"id": "POL-1", "text": "Policy text"}], "citations": ["POL-1"]},
    )
    monkeypatch.setattr(main.store, "save_trace", lambda trace: None)

    client = TestClient(main.app)

    direct = client.post("/api/v1/ai/chat", json={"query": "What is the meal policy?"})
    assert direct.status_code == 200
    assert "travel_context" not in direct.json()

    contextual = client.post(
        "/api/v1/ai/chat",
        json={
            "query": "What is the hotel limit?",
            "grade": "G3",
            "travel_context": {"destination_country": "Japan", "employee_grade": "G3"},
        },
    )
    assert contextual.status_code == 200
    assert contextual.json()["travel_context"] == {"destination_country": "Japan", "employee_grade": "G3"}
