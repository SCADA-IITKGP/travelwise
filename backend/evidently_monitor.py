"""Evidently AI report generation and stage-by-stage observability diagnostics."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

os.environ.setdefault("DO_NOT_TRACK", "1")
os.environ.setdefault("EVIDENTLY_DISABLE_TELEMETRY", "1")

import pandas as pd

from . import embeddings, llm, market_data, rag, safety, store
from .agents import PROMPT_STRATEGIES, SYSTEM_PROMPT, run_agent
from .config import MAX_AGENT_STEPS, ROOT

RESULTS_DIR = ROOT / "evaluation" / "results"
EVAL_JSON_PATH = RESULTS_DIR / "evaluation.json"
BASELINE_JSON_PATH = RESULTS_DIR / "baseline.json"
GOLD_CASES_PATH = ROOT / "evaluation" / "gold_cases.json"


def _load_json(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _build_dataframe(source: str) -> tuple[pd.DataFrame, list[str], list[str], list[str]]:
    if source == "traces":
        rows = store.list_traces(500)
        records = []
        for row in rows:
            detail = {}
            try:
                detail = json.loads(row.get("trace_json") or "{}")
            except Exception:
                detail = {}
            records.append(
                {
                    "trace_id": row.get("trace_id", ""),
                    "status": row.get("status", "unknown"),
                    "failure_category": row.get("failure_category") or "none",
                    "prompt_strategy": detail.get("prompt_strategy") or "v3_structured_critic",
                    "critic_passed": str(detail.get("critic", {}).get("passed", True)),
                    "latency_ms": float(row.get("latency_ms") or 0.0),
                    "steps": int(row.get("steps") or 0),
                    "citation_count": len(detail.get("citations") or []),
                    "query": row.get("query") or "",
                    "answer": row.get("answer") or "",
                }
            )
        df = pd.DataFrame(records)
        if df.empty:
            df = pd.DataFrame(
                [
                    {
                        "trace_id": "SAMPLE-EMPTY",
                        "status": "no_traces_yet",
                        "failure_category": "none",
                        "prompt_strategy": "v3_structured_critic",
                        "critic_passed": "True",
                        "latency_ms": 0.0,
                        "steps": 0,
                        "citation_count": 0,
                        "query": "No assistant queries recorded yet.",
                        "answer": "Submit a policy question in Policy assistant to populate live trace monitoring.",
                    }
                ]
            )
        return (
            df,
            ["query", "answer"],
            ["latency_ms", "steps", "citation_count"],
            ["status", "failure_category", "prompt_strategy", "critic_passed"],
        )

    eval_data = _load_json(EVAL_JSON_PATH)
    gold_cases = {c["id"]: c for c in (_load_json(GOLD_CASES_PATH) or [])}
    eval_rows = (eval_data or {}).get("results", [])
    records = []
    for item in eval_rows:
        case = gold_cases.get(item["id"], {})
        records.append(
            {
                "case_id": item["id"],
                "suite": item.get("suite", "golden_qa"),
                "critical": str(bool(item.get("critical"))),
                "status": item.get("status", "unknown"),
                "citation_hit": str(item.get("citation_hit")),
                "security_ok": str(bool(item.get("security_ok"))),
                "score": float(item.get("score") or 0.0),
                "latency_ms": float(item.get("latency_ms") or 0.0),
                "query": case.get("query", ""),
                "expected_answer": case.get("expected_answer", ""),
            }
        )
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(
            [
                {
                    "case_id": "G01",
                    "suite": "golden_qa",
                    "critical": "False",
                    "status": "not_run",
                    "citation_hit": "None",
                    "security_ok": "True",
                    "score": 0.0,
                    "latency_ms": 0.0,
                    "query": "Run evaluation.run_evaluation to populate 70-case metrics.",
                    "expected_answer": "Evaluation pending.",
                }
            ]
        )
    return (
        df,
        ["query", "expected_answer"],
        ["score", "latency_ms"],
        ["suite", "critical", "status", "citation_hit", "security_ok"],
    )


def generate_report(source: str = "evaluation") -> dict:
    """Build and export an Evidently 0.7.x HTML + JSON report for evaluation or live traces."""
    if source not in {"evaluation", "traces"}:
        raise ValueError("Evidently report source must be 'evaluation' or 'traces'.")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    html_path = RESULTS_DIR / f"evidently_{source}_report.html"
    summary_path = RESULTS_DIR / f"evidently_{source}_summary.json"

    df, text_cols, num_cols, cat_cols = _build_dataframe(source)

    import evidently
    from evidently import DataDefinition, Dataset, Report
    from evidently.descriptors import TextLength, WordCount
    from evidently.presets import DataSummaryPreset, TextEvals

    primary_text = text_cols[1] if len(text_cols) > 1 else text_cols[0]
    descriptors = [
        TextLength(text_cols[0], alias="Query Characters"),
        WordCount(text_cols[0], alias="Query Words"),
        TextLength(primary_text, alias="Response Characters"),
        WordCount(primary_text, alias="Response Words"),
    ]
    dataset = Dataset.from_pandas(
        df,
        data_definition=DataDefinition(
            text_columns=text_cols,
            numerical_columns=num_cols,
            categorical_columns=cat_cols,
        ),
        descriptors=descriptors,
    )
    report = Report([DataSummaryPreset(), TextEvals()])
    snapshot = report.run(dataset, None)
    snapshot.save_html(str(html_path))

    raw_dict = snapshot.dict()
    metric_summaries = []
    for metric in raw_dict.get("metrics", [])[:12]:
        metric_summaries.append(
            {
                "id": metric.get("id"),
                "metric_name": metric.get("metric_name"),
                "value": metric.get("value"),
            }
        )

    summary = {
        "source": source,
        "evidently_version": evidently.__version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "row_count": int(len(df)),
        "columns": list(df.columns),
        "descriptors": [d.alias for d in descriptors],
        "html_report_path": str(html_path.relative_to(ROOT)) if html_path.is_relative_to(ROOT) else str(html_path),
        "report_url": f"/api/v1/observability/evidently/report?source={source}",
        "metrics_count": len(raw_dict.get("metrics", [])),
        "metrics_preview": metric_summaries,
    }
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary


def get_summary(source: str = "evaluation") -> dict:
    if source not in {"evaluation", "traces"}:
        raise ValueError("Evidently report source must be 'evaluation' or 'traces'.")
    summary_path = RESULTS_DIR / f"evidently_{source}_summary.json"
    html_path = RESULTS_DIR / f"evidently_{source}_report.html"
    cached = _load_json(summary_path)
    if cached and html_path.is_file():
        return cached
    return generate_report(source)


def get_html_report(source: str = "evaluation") -> str:
    if source not in {"evaluation", "traces"}:
        raise ValueError("Evidently report source must be 'evaluation' or 'traces'.")
    html_path = RESULTS_DIR / f"evidently_{source}_report.html"
    if not html_path.is_file():
        generate_report(source)
    return html_path.read_text(encoding="utf-8")


def pipeline_overview() -> dict:
    """Return full architecture, model/embedding config, and evaluation results."""
    eval_data = _load_json(EVAL_JSON_PATH) or {}
    baseline_data = _load_json(BASELINE_JSON_PATH) or {}
    llm_st = llm.status()
    emb_st = embeddings.status()
    rag_st = rag.cache_status()
    fx_st = market_data.status()

    return {
        "levels": [
            {
                "level": 1,
                "name": "Safety, PII Redaction & Conditional Context",
                "module": "backend/safety.py + frontend/src/App.jsx",
                "how_it_works": "Inspects queries for prompt-injection overrides, redacts PII (email, phone, PAN, card), and checks whether travel context was selected before enriching or passing direct chat queries.",
                "metrics": {
                    "injection_rules": len(safety.INJECTION),
                    "pii_patterns": list(safety.PII.keys()),
                    "security_pass_rate": eval_data.get("security_pass_rate"),
                },
            },
            {
                "level": 2,
                "name": "Chunking, Hybrid Embeddings (bge-small-en-v1.5) & Reranking",
                "module": "backend/embeddings.py + backend/rag.py",
                "how_it_works": "Splits policy documents into bounded clauses, indexes with TF-IDF + Capstone bge-small-en-v1.5 (384-d vectors, 16 texts/batch, <=512 tokens), and reranks top candidates with phrase matching, historical-version demotion, and document diversity.",
                "metrics": {
                    "embedding_model": emb_st.get("model"),
                    "embedding_configured": emb_st.get("configured"),
                    "embedding_mode": emb_st.get("mode"),
                    "dimensions": emb_st.get("dimensions"),
                    "batch_size": emb_st.get("batch_size"),
                    "rag_cache": rag_st,
                    "baseline_recall_at_6": baseline_data.get("corpus_citation_recall_at_6"),
                    "baseline_mrr": baseline_data.get("mrr"),
                    "baseline_ndcg_at_6": baseline_data.get("ndcg_at_6"),
                    "eval_citation_recall_at_4": eval_data.get("corpus_citation_recall"),
                },
            },
            {
                "level": 3,
                "name": "Planner / Executor / Critic Loop & Session Memory",
                "module": "backend/agents.py + backend/store.py",
                "how_it_works": "Plans bounded tool calls (policy_search, receipt_extract, fx_rate, expense_validate), loads SQLite session memory, parses StructuredAgentOutput JSON, and runs a Critic check + single-step repair for citation grounding.",
                "metrics": {
                    "max_agent_steps": MAX_AGENT_STEPS,
                    "prompt_strategies": list(PROMPT_STRATEGIES.keys()),
                    "prompt_invariants_passed": (eval_data.get("prompt_verification") or {}).get("passed"),
                    "prompt_strategy_comparison": eval_data.get("prompt_strategy_comparison"),
                },
            },
            {
                "level": 4,
                "name": "Hosted LLM Inference (Qwen/Qwen3-8B) & Release Gate",
                "module": "backend/llm.py + evaluation/run_evaluation.py",
                "how_it_works": "Routes grounded prompts + sanitized evidence to Qwen/Qwen3-8B over HTTPS with CA cert verification (vm04-ca.crt), 55/min rate guard, 429/503 retries, or serves Evidence-only retrieval when unconfigured.",
                "metrics": {
                    "active_selection": llm_st.get("active_selection"),
                    "model": llm_st.get("model"),
                    "mode": llm_st.get("mode"),
                    "configured": llm_st.get("configured"),
                    "endpoint_url": llm_st.get("endpoint_url"),
                    "ca_certificate_configured": llm_st.get("ca_certificate_configured"),
                    "total_calls": llm_st.get("total_calls"),
                    "fx_cache": fx_st,
                    "release_gate": eval_data.get("release_gate"),
                },
            },
        ],
        "system_prompt_chars": len(SYSTEM_PROMPT),
    }


async def run_pipeline_diagnostic(
    query: str = "What receipts are required for expense reimbursement?",
    organization_id: str = "globaltech",
    travel_context: dict | None = None,
) -> dict:
    """Execute one query and return structured per-level results for Operations inspection."""
    t0 = time.perf_counter()
    blocked = safety.inspect_query(query)
    redacted = safety.redact_pii(query)
    level_1 = {
        "level": 1,
        "name": "Safety & Conditional Context",
        "status": "blocked" if blocked else "passed",
        "blocked_reason": blocked,
        "redacted_query": redacted,
        "context_applied": bool(travel_context),
        "travel_context": travel_context or {},
        "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
    }

    t1 = time.perf_counter()
    docs = [] if blocked else rag.retrieve(query, grade=(travel_context or {}).get("employee_grade") or "ALL", top_k=4, organization_id=organization_id)
    level_2 = {
        "level": 2,
        "name": "Retrieval, Embeddings & Reranking",
        "status": "skipped" if blocked else ("success" if docs else "empty"),
        "embedding_model": embeddings.current_model(),
        "embedding_active": embeddings.is_configured(),
        "retrieval_mode": embeddings.current_mode() if embeddings.is_configured() else "tfidf_rerank",
        "documents_found": len(docs),
        "top_documents": [
            {
                "id": d["id"],
                "document_id": d.get("document_id"),
                "title": d.get("title"),
                "score": d.get("score"),
            }
            for d in docs
        ],
        "duration_ms": round((time.perf_counter() - t1) * 1000, 2),
    }

    trace = await run_agent(
        query,
        "OPS-DIAG",
        grade=(travel_context or {}).get("employee_grade"),
        organization_id=organization_id,
        travel_context=travel_context,
    )
    level_3 = {
        "level": 3,
        "name": "Agent Orchestration & Critic",
        "status": trace.get("status"),
        "plan": trace.get("plan", []),
        "steps_log": trace.get("steps_log", []),
        "structured_output_valid": trace.get("structured_output_valid"),
        "critic": trace.get("critic"),
        "citations": trace.get("citations", []),
    }
    level_4 = {
        "level": 4,
        "name": "Model Output & Verification",
        "llm_mode": llm.current_mode(),
        "model": llm.status().get("model"),
        "answer": trace.get("answer"),
        "failure_category": trace.get("failure_category"),
        "latency_ms": trace.get("latency_ms"),
    }
    return {
        "trace_id": trace.get("trace_id"),
        "organization_id": organization_id,
        "levels": [level_1, level_2, level_3, level_4],
    }
