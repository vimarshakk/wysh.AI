"""Fail-closed study-enablement gate for R16 external evidence."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[3]
REQUIRED_DOCS = [
    "docs/R16_STUDY_ENABLEMENT_PROGRAM.md",
    "docs/R16_REVIEWER_AND_COI_CONTROLS.md",
    "docs/R16_DATA_ACCESS_AND_RIGHTS.md",
    "docs/R16_REFERENCE_STANDARDS_AND_ADJUDICATION.md",
    "docs/R16_ETHICS_REGULATORY_APPROVALS.md",
    "docs/R16_FROZEN_PROTOCOL_AND_STOP_RULES.md",
    "docs/R16_INDEPENDENT_READINESS_REVIEW.md",
    "docs/R16_VALIDATION_READINESS_ACCEPTANCE.md",
]


def main() -> int:
    missing = [path for path in REQUIRED_DOCS if not (ROOT / path).is_file()]
    contents = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in REQUIRED_DOCS if (ROOT / path).is_file())
    boundary_checks = {
        "no recruitment asserted": "no reviewer recruitment" in contents.lower(),
        "no real dataset asserted": "no non-synthetic dataset" in contents.lower(),
        "no ethics approval asserted": "no ethics approval" in contents.lower(),
        "no regulatory classification asserted": "not legal advice or a regulatory classification" in contents.lower(),
        "no-go defined": "`NO-GO`" in contents,
    }
    engineering_ready = not missing and all(boundary_checks.values())
    report = {
        "schema_version": "r16-gate-v1",
        "milestone": "R16A-R16F",
        "status": "ENGINEERING_READY_ONLY" if engineering_ready else "BLOCKED",
        "required_documents": {"count": len(REQUIRED_DOCS), "present": len(REQUIRED_DOCS) - len(missing), "missing": missing},
        "boundary_checks": boundary_checks,
        "engineering_readiness": engineering_ready,
        "reviewer_qualifications_verified": False,
        "independence_and_coi_verified": False,
        "dataset_access_and_rights_verified": False,
        "clinical_reference_standards_verified": False,
        "ethics_and_regulatory_pathway_verified": False,
        "frozen_protocol_verified": False,
        "independent_readiness_decision": "NO-GO",
        "study_ready": False,
        "clinically_validated": False,
        "score": 69,
        "score_delta": 0,
        "clinical_governance": "HOLD",
        "clinical_validation": "NO-GO",
        "production": "NO-GO",
        "wyshcare_modified": False,
        "external_actions_taken": False,
        "release_decision": "Do not recruit, request/access real data, submit approvals, initiate a study, or authorize clinical use under R16 engineering scope.",
    }
    output = ROOT / "artifacts/r16-test-evidence/r16-gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "study_ready": report["study_ready"], "output": str(output)}))
    return 0 if engineering_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
