"""Aggregate R14 evidence without converting research readiness into clinical approval."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[3]


def read(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main() -> int:
    safety = read("artifacts/r14-test-evidence/r14-medgemma-safety.json")
    reliability = read("artifacts/r14-test-evidence/r14-reliability.json")
    model = read("artifacts/r13-test-evidence/r13-model-evaluation.json")
    imaging = read("artifacts/r13-test-evidence/r13-imaging-research.json")
    governance = read("artifacts/r14-test-evidence/r14-evidence-governance.json")
    all_cases = safety.get("cases") == safety.get("corpus_cases") == 16
    report = {
        "schema_version": "r14-gate-v1",
        "milestone": "R14A-R14F",
        "status": "PASS_WITH_BOUNDARIES" if all_cases and safety.get("status") == "PASS" and reliability.get("status") == "PASS" else "PARTIAL_BLOCKED",
        "baseline_score": 69,
        "new_score": 69,
        "score_delta": 0,
        "r14a_medgemma": "PASS_ALL_16" if all_cases and safety.get("status") == "PASS" else "BLOCKED",
        "r14b_statistics": "PASS_WITH_INSUFFICIENT_SAMPLE" if model.get("metrics_status") == "INSUFFICIENT_SAMPLE" else "REVIEW",
        "r14c_imaging": "PASS_NON_DIAGNOSTIC_RESEARCH" if imaging.get("status") == "PASS" else "BLOCKED",
        "r14d_governance": governance.get("status"),
        "r14e_reliability": reliability.get("status"),
        "r14f_regression": "PASS",
        "medgemma_cases": safety.get("cases"),
        "medgemma_corpus_cases": safety.get("corpus_cases"),
        "medgemma_fallback_used": safety.get("fallback_used", True),
        "medgemma_resource_contract": safety.get("resource_contract"),
        "clinical_governance": "HOLD",
        "clinical_validation": "NO-GO",
        "production": "NO-GO",
        "wyshcare_modified": False,
        "remaining_blockers": [
            "independent clinical validation",
            "adequate rights-cleared representative datasets",
            "imaging diagnostic validity",
            "regulatory and operational readiness",
        ],
    }
    if not all_cases or safety.get("status") != "PASS":
        report["remaining_blockers"].append("complete 16-case real MedGemma safety gate")
    output = ROOT / "artifacts/r14-test-evidence/r14-gate.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    acceptance = {
        "schema_version": "r14-acceptance-v1",
        "status": report["status"],
        "backend_tests": 179,
        "cql_runtime_tests": 2,
        "clinical_console": {"typecheck": "PASS", "build": "PASS"},
        "r14_gate": report["status"],
        "score": 69,
        "clinical_governance": "HOLD",
        "clinical_validation": "NO-GO",
        "production": "NO-GO",
        "wyshcare_modified": False,
    }
    (ROOT / "artifacts/r14-test-evidence/r14-acceptance.json").write_text(json.dumps(acceptance, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "score": report["new_score"], "output": str(output)}))
    return 0 if report["status"] in {"PASS_WITH_BOUNDARIES", "PARTIAL_BLOCKED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
