"""Fail-closed validation-readiness audit for R15 engineering preparation."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[3]
DOCS = [
    "docs/R15_INTENDED_USE_AND_CLAIMS.md",
    "docs/R15_CLINICAL_VALIDATION_PROTOCOLS.md",
    "docs/R15_INDEPENDENT_REVIEW_AND_ADJUDICATION.md",
    "docs/R15_DATA_ETHICS_AND_REGULATORY_READINESS.md",
    "docs/R15_RISK_MANAGEMENT.md",
    "docs/R15_VALIDATION_READINESS_ACCEPTANCE.md",
]


def main() -> int:
    missing = [path for path in DOCS if not (ROOT / path).is_file()]
    text = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in DOCS if (ROOT / path).is_file())
    required_boundaries = ["NO-GO", "synthetic", "not a regulatory", "qualified", "not constitute clinical validation"]
    boundary_checks = {term: term.lower() in text.lower() for term in required_boundaries}
    docs_pass = not missing and all(boundary_checks.values())
    report = {
        "schema_version": "r15-gate-v1",
        "milestone": "R15A-R15F",
        "status": "ENGINEERING_READY_ONLY" if docs_pass else "BLOCKED",
        "document_checks": {"required_documents": len(DOCS), "present": len(DOCS) - len(missing), "missing": missing, "boundary_checks": boundary_checks},
        "engineering_ready": docs_pass,
        "study_ready": False,
        "clinically_validated": False,
        "qualified_reviewers_confirmed": False,
        "dataset_rights_confirmed": False,
        "ethics_approval_confirmed": False,
        "clinical_reference_standards_confirmed": False,
        "independent_study_authorized": False,
        "score": 69,
        "score_delta": 0,
        "clinical_governance": "HOLD",
        "clinical_validation": "NO-GO",
        "production": "NO-GO",
        "wyshcare_modified": False,
        "release_decision": "Preparation artifacts only; do not access real data or initiate a clinical study.",
    }
    output = ROOT / "artifacts/r15-test-evidence/r15-gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "score": report["score"], "output": str(output)}))
    return 0 if docs_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
