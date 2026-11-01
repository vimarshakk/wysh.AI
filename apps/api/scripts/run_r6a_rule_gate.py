"""Run the R6A evidence registry and diabetes rule vertical-slice gate."""

from __future__ import annotations

import json
from pathlib import Path

from app.approved_clinical_rules import evaluate_diabetes_hypoglycemia
from app.disease_specific_intelligence import DiseaseSpecificRequest
from app.disease_intelligence import LongitudinalMeasurement


def observation(mid: str, value: float, unit: str = "mg/dL") -> LongitudinalMeasurement:
    return LongitudinalMeasurement(measurement_id=mid, metric="glucose", value=value, unit=unit, observed_at="2026-01-01T00:00:00Z", source_type="observation")


def main() -> int:
    root = Path(__file__).parents[3]
    registry = json.loads((root / "disease-intelligence/evidence/clinical-evidence-registry-v1.json").read_text())
    entry = registry["entries"][0]
    request = lambda measurements: DiseaseSpecificRequest(tenant_id="synthetic-r6a-tenant", patient_id="synthetic-r6a-patient", disease_id="diabetes", measurements=measurements, synthetic=True)
    low = evaluate_diabetes_hypoglycemia(request([observation("g1", 69)]))
    severe = evaluate_diabetes_hypoglycemia(request([observation("g2", 53)]))
    boundary = evaluate_diabetes_hypoglycemia(request([observation("g3", 70)]))
    missing = evaluate_diabetes_hypoglycemia(request([LongitudinalMeasurement(measurement_id="a1", metric="hba1c", value=6.5, unit="%", observed_at="2026-01-01T00:00:00Z", source_type="laboratory")]))
    checks = {
        "registry_schema_version": registry.get("schema_version") == "clinical-evidence-registry-v1",
        "source_metadata_only": entry.get("content_copied") is False,
        "clinical_approval_not_fabricated": entry.get("approval_status") == "ENGINEERING_ONLY" and entry.get("clinical_reviewer") is None,
        "level_one_boundary_triggers_review": low.findings[0].status == "TRIGGERED",
        "level_two_boundary_triggers_review": severe.findings[0].status == "TRIGGERED",
        "boundary_at_70_not_triggered": boundary.findings[0].status == "NOT_TRIGGERED",
        "missing_glucose_abstains": missing.abstained is True,
        "clinical_use_disabled": low.clinical_use_authorized is False,
    }
    payload = {"suite": "synthetic-r6a-clinical-rule-gate", "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "rule_id": "diabetes.hypoglycemia-observation", "approval_status": low.approval_status, "clinical_validation": "NO-GO", "synthetic_only": True}
    output = root / "artifacts/r6-test-evidence/r6a-rule-gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), **payload}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
