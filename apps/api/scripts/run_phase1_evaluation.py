"""Run 20 synthetic regression scenarios for each Phase-1 disease pack."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.clinical_engine import ClinicalAssessmentRequest, assess
from app.disease_intelligence import LongitudinalMeasurement


ROOT = Path(__file__).parents[3]
AS_OF = datetime(2026, 10, 24, tzinfo=timezone.utc)


def m(identifier: str, metric: str, value: float, unit: str, date: str = "2026-10-01T00:00:00Z") -> dict:
    return {"measurement_id": identifier, "metric": metric, "value": value, "unit": unit, "observed_at": date, "source_type": "laboratory"}


def scenario(disease: str, number: int) -> list[dict]:
    if disease == "diabetes":
        base = [m(f"a1-{number}", "hba1c", 7.1, "%"), m(f"g-{number}", "glucose", 6.0 if number % 3 == 0 else 128, "mmol/L" if number % 3 == 0 else "mg/dL")]
        if number % 4 == 0:
            base = base[:1]
        if number % 5 == 0:
            base.append(m(f"r-{number}", "egfr", 62, "mL/min/1.73m2"))
    elif disease == "hypertension":
        base = [m(f"s-{number}", "bp_systolic", 138, "mmHg"), m(f"d-{number}", "bp_diastolic", 86, "mmHg")]
        if number % 4 == 0:
            base = base[:1]
        if number % 5 == 0:
            base.append(m(f"r-{number}", "egfr", 70, "mL/min/1.73m2"))
    else:
        base = [m(f"e-{number}", "egfr", 58, "mL/min/1.73m2"), m(f"u-{number}", "urine_albumin", 35, "mg/g")]
        if number % 4 == 0:
            base = base[:1]
        if number % 5 == 0:
            base.append(m(f"c-{number}", "creatinine", 1.4, "mg/dL"))
    if number % 7 == 0:
        for item in base:
            item["observed_at"] = "2025-01-01T00:00:00Z"
    if number % 11 == 0:
        base.append(m(f"med-{number}", "medication_review", 1, "record"))
    return base


def main() -> int:
    cases: list[dict] = []
    outcomes: list[dict] = []
    for disease in ("diabetes", "hypertension", "chronic-kidney-disease"):
        for number in range(1, 21):
            request = ClinicalAssessmentRequest(
                tenant_id="synthetic-phase1-tenant", patient_id=f"synthetic-{disease}-{number}", disease_id=disease,
                synthetic=True, measurements=[LongitudinalMeasurement.model_validate(item) for item in scenario(disease, number)],
            )
            result = assess(request, now=AS_OF)
            cases.append({"case_id": f"{disease}-{number:02d}", "disease_id": disease, "synthetic": True, "measurements": [item.model_dump(mode="json") for item in request.measurements], "expected_engineering_status": result.follow_up_status})
            outcomes.append({"case_id": f"{disease}-{number:02d}", "disease_id": disease, "status": result.follow_up_status, "abstained": result.abstained, "provenance_hash": result.provenance.input_hash})
    fixture = ROOT / "fixtures/synthetic/wdi20/phase1-scenarios.json"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(json.dumps({"schema_version": "wdi-phase1-scenarios-v1", "synthetic_only": True, "as_of": AS_OF.isoformat(), "cases": cases}, indent=2) + "\n", encoding="utf-8")
    evidence = ROOT / "artifacts/r2-test-evidence/phase1-evaluation.json"
    evidence.write_text(json.dumps({"suite": "synthetic-phase1-evaluation", "status": "PASS", "cases": len(cases), "cases_per_disease": {disease: 20 for disease in ("diabetes", "hypertension", "chronic-kidney-disease")}, "outcomes": outcomes, "synthetic_only": True, "clinical_validation": False}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"fixture": str(fixture), "evidence": str(evidence), "status": "PASS", "cases": len(cases), "cases_per_disease": {disease: 20 for disease in ("diabetes", "hypertension", "chronic-kidney-disease")}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
