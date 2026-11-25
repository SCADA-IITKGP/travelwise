"""Retrieval-only baseline across the golden evaluation dataset."""

import json
import pathlib
import subprocess
import time

from backend.rag import retrieve
from backend.safety import inspect_query

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _doc_id(citation_id):
    return citation_id.split("#", 1)[0]


def main():
    cases = json.loads((ROOT / "evaluation/gold_cases.json").read_text(encoding="utf-8"))
    out = []
    for c in cases:
        t = time.perf_counter()
        blocked = inspect_query(c["query"])
        org = c.get("organization_id", "globaltech")
        docs = [] if blocked else retrieve(c["query"], c.get("grade", "ALL"), top_k=6, organization_id=org)
        retrieved_doc_ids = list(dict.fromkeys(_doc_id(d["id"]) for d in docs))
        exp = c.get("expected_citations", [])
        citation_hit = any(item in retrieved_doc_ids for item in exp) if exp else None
        out.append(
            {
                "id": c["id"],
                "suite": c.get("suite", "golden_qa"),
                "organization_id": org,
                "retrieved_ids": [d["id"] for d in docs],
                "retrieved_doc_ids": retrieved_doc_ids,
                "expected_citations": exp,
                "citation_hit": citation_hit,
                "blocked": bool(blocked),
                "latency_ms": round((time.perf_counter() - t) * 1000, 2),
            }
        )
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        commit = "not-in-git-yet"
    with_citations = [x for x in out if x["citation_hit"] is not None]
    result = {
        "dataset_version": "globaltech-v1-70cases",
        "git_commit": commit,
        "mode": "retrieval_only_baseline",
        "total_cases": len(out),
        "corpus_covered_cases": len(with_citations),
        "corpus_citation_recall_at_6": round(
            sum(1 for x in with_citations if x["citation_hit"]) / len(with_citations), 4
        )
        if with_citations
        else 0.0,
        "results": out,
    }
    dest = ROOT / "evaluation/results"
    dest.mkdir(exist_ok=True)
    (dest / "baseline.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
