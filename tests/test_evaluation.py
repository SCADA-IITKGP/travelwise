import json
from pathlib import Path

from backend.agents import SYSTEM_PROMPT
from backend.safety import inspect_query
from evaluation.run_evaluation import _evaluate_hosted_answer, verify_prompt

ROOT = Path(__file__).resolve().parents[1]


def test_gold_cases_dataset_structure():
    cases = json.loads((ROOT / "evaluation/gold_cases.json").read_text(encoding="utf-8"))
    ids = [c["id"] for c in cases]
    assert len(cases) == 70
    assert [f"G{i:02d}" for i in range(1, 51)] == ids[:50]
    assert [f"T{i:02d}" for i in range(1, 21)] == ids[50:]
    critical_ids = {c["id"] for c in cases if c.get("critical")}
    assert critical_ids == {"T04", "T05", "T07", "T08", "T09", "T10", "T11", "T18", "T20"}


def test_prompt_invariants_pass():
    report = verify_prompt(SYSTEM_PROMPT)
    assert report["passed"] is True


def test_safety_injection_catches_t07_without_false_positives():
    cases = {c["id"]: c for c in json.loads((ROOT / "evaluation/gold_cases.json").read_text(encoding="utf-8"))}
    assert inspect_query(cases["T07"]["query"]) == "security_prompt_injection"
    for cid in ("T04", "T05", "T10", "T14", "G03", "G17"):
        assert inspect_query(cases[cid]["query"]) is None


def test_hosted_rubric_scoring_flags_fabrication_and_rewards_grounded_refusal():
    cases = {c["id"]: c for c in json.loads((ROOT / "evaluation/gold_cases.json").read_text(encoding="utf-8"))}
    score_fail, _ = _evaluate_hosted_answer(
        cases["T12"],
        {"status": "success", "answer": "Call +1 800-555-0199 for 24/7 support.", "citations": ["GT-TRV-OPS-014#clause-1"]},
    )
    assert score_fail == 0

    score_pass, _ = _evaluate_hosted_answer(
        cases["T04"],
        {
            "status": "success",
            "answer": "No, splitting transactions to stay below approval thresholds is prohibited [GT-TRV-EXP-025].",
            "citations": ["GT-TRV-EXP-025#clause-1"],
        },
    )
    assert score_pass == 2
