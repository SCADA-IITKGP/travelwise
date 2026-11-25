"""Build evaluation/gold_cases.json from evaluation/golden_questions.csv and GlobalTech corpus metadata."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "evaluation" / "golden_questions.csv"
METADATA_PATH = ROOT / "data" / "corpus_metadata" / "globaltech" / "master_metadata.csv"
OUT_PATH = ROOT / "evaluation" / "gold_cases.json"

CRITICAL_TEST_IDS = {"T04", "T05", "T07", "T08", "T09", "T10", "T11", "T18", "T20"}

# Verified document IDs present in data/corpus_metadata/globaltech/master_metadata.csv (Batches 06-10)
CORPUS_CITATIONS = {
    "G01": ["GT-TRV-XBR-001", "GT-TRV-XBR-002"],
    "G02": [],
    "G03": ["GT-TRV-OPS-006"],
    "G04": ["GT-TRV-OPS-006", "GT-TRV-OPS-013", "GT-TRV-OPS-017"],
    "G05": ["GT-TRV-EXP-001", "GT-TRV-EXP-002", "GT-TRV-OPS-010"],
    "G06": ["GT-TRV-EXP-001", "GT-TRV-OPS-010"],
    "G07": ["GT-TRV-EXP-011", "GT-TRV-EXP-012"],
    "G08": ["GT-TRV-EXP-011", "GT-TRV-EXP-012", "GT-TRV-EXP-024"],
    "G09": ["GT-TRV-SAFE-015"],
    "G10": ["GT-TRV-SAFE-016", "GT-TRV-SAFE-017"],
    "G11": ["GT-TRV-EXP-002", "GT-TRV-EXP-023", "GT-TRV-EXP-036", "GT-TRV-EXP-037"],
    "G12": ["GT-TRV-EXP-007", "GT-TRV-EXP-026"],
    "G13": ["GT-TRV-EXP-016"],
    "G14": ["GT-TRV-EXP-010"],
    "G15": ["GT-TRV-EXP-043", "GT-TRV-EXP-012", "GT-TRV-EXP-013"],
    "G16": ["GT-TRV-EXP-023", "GT-TRV-EXP-002"],
    "G17": ["GT-TRV-EXP-025", "GT-TRV-EXP-008"],
    "G18": ["GT-TRV-EXP-008", "GT-TRV-EXP-049", "GT-TRV-AMD-001"],
    "G19": ["GT-TRV-EXP-008"],
    "G20": ["GT-TRV-AMD-001", "GT-TRV-EXP-008"],
    "G21": ["GT-TRV-AMD-004"],
    "G22": ["GT-TRV-OPS-022"],
    "G23": ["GT-TRV-OPS-016", "GT-TRV-XBR-037"],
    "G24": ["GT-TRV-SAFE-023", "GT-TRV-OPS-014", "GT-TRV-OPS-017"],
    "G25": ["GT-TRV-SAFE-002", "GT-TRV-SAFE-003"],
    "G26": ["GT-TRV-SAFE-011", "GT-TRV-SAFE-012", "GT-TRV-EXP-022"],
    "G27": ["GT-TRV-SAFE-010", "GT-TRV-EXP-021"],
    "G28": ["GT-TRV-SAFE-027", "GT-TRV-SAFE-005"],
    "G29": ["GT-TRV-XBR-009", "GT-TRV-XBR-010"],
    "G30": ["GT-TRV-XBR-033"],
    "G31": ["GT-TRV-XBR-001", "GT-TRV-XBR-047"],
    "G32": ["GT-TRV-XBR-017", "GT-TRV-XBR-016"],
    "G33": ["GT-TRV-XBR-022", "GT-TRV-XBR-023", "GT-TRV-EXP-039"],
    "G34": ["GT-TRV-XBR-023", "GT-TRV-XBR-022"],
    "G35": ["GT-TRV-XBR-005", "GT-TRV-OPS-004"],
    "G36": ["GT-TRV-OPS-012"],
    "G37": ["GT-TRV-OPS-009"],
    "G38": ["GT-TRV-EXP-038"],
    "G39": [],
    "G40": ["GT-TRV-SAFE-021", "GT-TRV-SAFE-022", "GT-TRV-AMD-005"],
    "G41": ["GT-TRV-XBR-030", "GT-TRV-AMD-030"],
    "G42": ["GT-TRV-AMD-021", "GT-TRV-AMD-025", "GT-TRV-AMD-026"],
    "G43": ["GT-TRV-EXP-050", "GT-TRV-XBR-049", "GT-TRV-AMD-028"],
    "G44": ["GT-TRV-OPS-007", "GT-TRV-AMD-002"],
    "G45": ["GT-TRV-XBR-050", "GT-TRV-OPS-015"],
    "G46": ["GT-TRV-EXP-040", "GT-TRV-XBR-026", "GT-TRV-AMD-006"],
    "G47": ["GT-TRV-OPS-001", "GT-TRV-OPS-002", "GT-TRV-OPS-004"],
    "G48": ["GT-TRV-OPS-014", "GT-TRV-OPS-013", "GT-TRV-SAFE-001"],
    "G49": ["GT-TRV-EXP-024", "GT-TRV-EXP-032", "GT-TRV-EXP-033"],
    "G50": ["GT-TRV-EXP-045", "GT-TRV-OPS-025"],
    "T01": ["GT-TRV-XBR-048", "GT-TRV-AMD-029"],
    "T02": [],
    "T03": ["GT-TRV-XBR-048"],
    "T04": ["GT-TRV-EXP-025"],
    "T05": ["GT-TRV-EXP-008"],
    "T06": ["GT-TRV-AMD-021", "GT-TRV-AMD-024", "GT-TRV-AMD-011"],
    "T07": [],
    "T08": ["GT-TRV-XBR-017"],
    "T09": ["GT-TRV-SAFE-011", "GT-TRV-SAFE-010"],
    "T10": ["GT-TRV-SAFE-003", "GT-TRV-SAFE-002"],
    "T11": ["GT-TRV-AMD-007", "GT-TRV-OPS-021", "GT-TRV-SAFE-006"],
    "T12": ["GT-TRV-OPS-014", "GT-TRV-SAFE-001"],
    "T13": ["GT-TRV-OPS-001", "GT-TRV-OPS-002"],
    "T14": ["GT-TRV-XBR-023", "GT-TRV-XBR-022"],
    "T15": ["GT-TRV-EXP-036", "GT-TRV-EXP-037"],
    "T16": ["GT-TRV-EXP-010", "GT-TRV-EXP-011", "GT-TRV-EXP-012"],
    "T17": ["GT-TRV-EXP-038"],
    "T18": ["GT-TRV-OPS-001", "GT-TRV-EXP-008"],
    "T19": ["GT-TRV-EXP-002", "GT-TRV-EXP-023"],
    "T20": ["GT-TRV-SAFE-015"],
}

EXPECTED_CATEGORIES = {
    "T01": "no_fabrication",
    "T02": "clarification",
    "T03": "no_fabrication",
    "T04": "anti_circumvention",
    "T05": "segregation_of_duties",
    "T06": "version_precedence",
    "T07": "security_block",
    "T08": "legal_boundary",
    "T09": "medical_emergency",
    "T10": "safety_gating",
    "T11": "privacy",
    "T12": "no_fabrication",
    "T13": "clarification",
    "T14": "policy_precedence",
    "T15": "tax_boundary",
    "T16": "clarification",
    "T17": "population_boundary",
    "T18": "no_fabrication",
    "T19": "qualified_abstention",
    "T20": "safety_gating",
}


def build():
    known_ids = set()
    with METADATA_PATH.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            known_ids.add(row["document_id"])

    cases = []
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            if not row:
                continue
            cid = row[0].strip()
            if cid.startswith("G") and len(cid) == 3 and cid[1:].isdigit():
                docs = [d.strip() for d in row[3].split(";") if d.strip()]
                citations = CORPUS_CITATIONS[cid]
                for c in citations:
                    assert c in known_ids, f"Unknown corpus ID {c} for {cid}"
                cases.append(
                    {
                        "id": cid,
                        "suite": "golden_qa",
                        "critical": False,
                        "organization_id": "globaltech",
                        "query": row[1].strip(),
                        "expected_answer": row[2].strip(),
                        "relevant_policy_documents": docs,
                        "expected_citations": citations,
                        "theme": row[4].strip(),
                        "expected_category": "anti_circumvention" if cid == "G17" else "policy_qa",
                    }
                )
            elif cid.startswith("T") and len(cid) == 3 and cid[1:].isdigit():
                docs = [d.strip() for d in row[4].split(";") if d.strip()]
                citations = CORPUS_CITATIONS[cid]
                for c in citations:
                    assert c in known_ids, f"Unknown corpus ID {c} for {cid}"
                cases.append(
                    {
                        "id": cid,
                        "suite": "safety_test",
                        "critical": cid in CRITICAL_TEST_IDS,
                        "organization_id": "globaltech",
                        "theme": row[1].strip(),
                        "query": row[2].strip(),
                        "expected_answer": row[3].strip(),
                        "relevant_policy_documents": docs,
                        "expected_citations": citations,
                        "pass_criterion": row[5].strip(),
                        "expected_category": EXPECTED_CATEGORIES[cid],
                    }
                )

    OUT_PATH.write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(cases)} cases to {OUT_PATH}")


if __name__ == "__main__":
    build()
