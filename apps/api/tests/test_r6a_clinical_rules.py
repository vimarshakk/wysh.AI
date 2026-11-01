from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import make_test_token
from app.approved_clinical_rules import evaluate_diabetes_hypoglycemia
from app.config import Settings
from app.disease_specific_intelligence import DiseaseSpecificRequest
from app.disease_intelligence import LongitudinalMeasurement
from app.main import create_app


def m(mid: str, value: float, unit: str = "mg/dL", observed_at: str = "2026-01-01T00:00:00Z") -> LongitudinalMeasurement:
    return LongitudinalMeasurement(measurement_id=mid, metric="glucose", value=value, unit=unit, observed_at=observed_at, source_type="observation")


def request(measurements: list[LongitudinalMeasurement], disease_id: str = "diabetes") -> DiseaseSpecificRequest:
    return DiseaseSpecificRequest(tenant_id="synthetic-r6-tenant", patient_id="synthetic-r6-patient", disease_id=disease_id, measurements=measurements, synthetic=True)


def test_evidence_registry_is_metadata_only_and_rule_is_not_clinically_approved():
    root = Path(__file__).parents[3]
    registry = json.loads((root / "disease-intelligence/evidence/clinical-evidence-registry-v1.json").read_text())
    assert registry["schema_version"] == "clinical-evidence-registry-v1"
    entry = registry["entries"][0]
    assert entry["content_copied"] is False
    assert entry["approval_status"] == "ENGINEERING_ONLY"
    assert entry["clinical_reviewer"] is None
    result = evaluate_diabetes_hypoglycemia(request([m("g1", 65)]))
    assert result.approval_status == "ENGINEERING_ONLY"
    assert result.findings[0].status == "TRIGGERED"
    assert "prescribe" in result.findings[0].blocked_actions


def test_rule_boundaries_units_missing_evidence_and_scope_fail_closed():
    level_one = evaluate_diabetes_hypoglycemia(request([m("g1", 69)]))
    level_two = evaluate_diabetes_hypoglycemia(request([m("g2", 53)]))
    boundary = evaluate_diabetes_hypoglycemia(request([m("g3", 70)]))
    assert level_one.findings[0].status == "TRIGGERED"
    assert level_two.findings[0].status == "TRIGGERED"
    assert boundary.findings[0].status == "NOT_TRIGGERED"
    mmol = evaluate_diabetes_hypoglycemia(request([m("g4", 3.0, "mmol/L")]))
    assert mmol.findings[0].status == "TRIGGERED"
    missing = evaluate_diabetes_hypoglycemia(request([LongitudinalMeasurement(measurement_id="a1", metric="hba1c", value=6.5, unit="%", observed_at="2026-01-01T00:00:00Z", source_type="laboratory")]))
    assert missing.abstained is True
    wrong_scope = evaluate_diabetes_hypoglycemia(request([m("g5", 65)], disease_id="hypertension"))
    assert wrong_scope.abstained is True


def test_rule_endpoint_requires_scope_and_remains_synthetic_only():
    app = create_app(Settings(service_token_secret="r6a-secret"))
    client = TestClient(app)
    token = make_test_token("r6a-secret", issuer="wyshcare", audience="wysh-ai", tenant_id="synthetic-r6-tenant", patient_ids=["synthetic-r6-patient"], scopes=["disease:rules"])
    body = {"tenant_id": "synthetic-r6-tenant", "patient_id": "synthetic-r6-patient", "disease_id": "diabetes", "synthetic": True, "measurements": [{"measurement_id": "g1", "metric": "glucose", "value": 65, "unit": "mg/dL", "observed_at": "2026-01-01T00:00:00Z", "source_type": "observation"}]}
    assert client.post("/v1/disease-intelligence/approved-rules/evaluate", json=body, headers={"Authorization": f"Bearer {token}"}).status_code == 200
    body["synthetic"] = False
    assert client.post("/v1/disease-intelligence/approved-rules/evaluate", json=body, headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_rule_hardening_abstains_on_conflict_and_stale_or_invalid_context():
    conflict = evaluate_diabetes_hypoglycemia(request([m("g1", 65), m("g2", 53)]))
    assert conflict.abstained is True
    assert conflict.findings[0].message.startswith("Conflicting glucose observations")
    duplicate = evaluate_diabetes_hypoglycemia(request([m("g1", 65), m("g2", 65)]))
    assert duplicate.abstained is False
    assert duplicate.findings[0].status == "NOT_TRIGGERED"
    stale_request = request([m("g3", 65)])
    stale_request.as_of = "2026-08-01T00:00:00Z"
    stale = evaluate_diabetes_hypoglycemia(stale_request)
    assert stale.abstained is True
    assert "stale" in stale.findings[0].message
    invalid_request = request([m("g4", 65)])
    invalid_request.as_of = "not-a-time"
    assert evaluate_diabetes_hypoglycemia(invalid_request).abstained is True


def test_rule_response_is_observation_classification_not_episode_diagnosis():
    result = evaluate_diabetes_hypoglycemia(request([m("g1", 54, "mmol/L")]))
    assert result.interpretation_scope == "OBSERVATION_CLASSIFICATION_ONLY"
    assert result.episode_diagnosis is False
