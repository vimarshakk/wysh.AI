"""Synthetic R4 integration evidence; no external services or PHI."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import make_test_token
from app.config import Settings
from app.main import create_app
from app.review_store import ReviewStore


def main() -> int:
    root = Path(__file__).parents[3]
    app = create_app(Settings(service_token_secret="r4-synthetic-secret"))
    app.state.review_store.close()
    app.state.review_store = ReviewStore(":memory:")
    client = TestClient(app)
    checks: dict[str, bool] = {}

    patients = client.get("/v1/console/synthetic-patients")
    checks["console_patient_index"] = patients.status_code == 200 and patients.json().get("synthetic_only") is True and len(patients.json().get("patients", [])) == 60
    case_id = patients.json().get("patients", [{}])[0].get("case_id")
    case = client.get(f"/v1/console/synthetic-patients/{case_id}")
    checks["console_patient_case"] = case.status_code == 200 and case.json().get("synthetic") is True
    measurements = case.json().get("measurements", [])
    assessment_payload = {"tenant_id": "synthetic-r4-tenant", "patient_id": "synthetic-r4-patient", "disease_id": "diabetes", "measurements": measurements, "synthetic": True}
    assessment = client.post("/v1/disease-intelligence/clinical-assess", json=assessment_payload)
    checks["assessment_provenance"] = assessment.status_code == 200 and assessment.json().get("provenance", {}).get("synthetic_only") is True

    calc = client.post("/v1/disease-intelligence/verified-calculations", json={**assessment_payload, "measurements": measurements + [{"measurement_id": "r4-hba1c", "metric": "hba1c", "value": 7.0, "unit": "%", "observed_at": "2026-01-01T00:00:00Z", "source_type": "laboratory"}]})
    checks["verified_calculation"] = calc.status_code == 200 and calc.json().get("provenance", {}).get("calculation_version") == "r4b-calculations-v1"

    cql = client.post("/v1/reuse-accelerator/ahrq-cql/execute", json={"tenant_id": "synthetic-r4-tenant", "patient_id": "synthetic-r4-patient", "library_id": "wysh.synthetic.rules.v1", "expression_id": "count-facts", "facts": [{"id": "f1", "metric": "glucose", "value": 120}], "synthetic": True})
    checks["bounded_cql_execution"] = cql.status_code == 200 and cql.json().get("status") == "EXECUTED_SYNTHETIC_SUBSET"

    token = make_test_token("r4-synthetic-secret", issuer="wyshcare", audience="wysh-ai", tenant_id="synthetic-r4-tenant", patient_ids=["synthetic-r4-patient"], scopes=["clinical-review:read", "clinical-review:write"], roles=["clinician"], subject="synthetic-clinician")
    headers = {"Authorization": f"Bearer {token}"}
    review = client.post("/v1/clinical-reviews", headers=headers, json={"tenant_id": "synthetic-r4-tenant", "patient_id": "synthetic-r4-patient", "disease_id": "diabetes", "assessment_id": assessment.json().get("assessment_id", "assessment-r4"), "assessment_input_hash": assessment.json().get("provenance", {}).get("input_hash", "a" * 64), "synthetic": True})
    decision = client.post(f"/v1/clinical-reviews/{review.json().get('review_id')}/decision", headers=headers, json={"tenant_id": "synthetic-r4-tenant", "patient_id": "synthetic-r4-patient", "expected_version": 1, "action": "request_revision", "note": "Synthetic evidence review.", "synthetic": True}) if review.status_code == 201 else None
    checks["persisted_review_create"] = review.status_code == 201 and review.json().get("state") == "DRAFT"
    checks["persisted_review_decision"] = decision is not None and decision.status_code == 200 and decision.json().get("state") == "REVISION_REQUESTED" and len(decision.json().get("events", [])) == 2

    payload = {"suite": "synthetic-r4-integrated-e2e", "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "clinical_accuracy_claim": False, "synthetic_only": True}
    output = root / "artifacts/r4-test-evidence/r4-integrated-e2e.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), **payload}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
