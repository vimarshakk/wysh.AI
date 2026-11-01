from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.clinical_engine import ClinicalAssessmentRequest, assess, normalize_measurements
from app.config import Settings
from app.disease_intelligence import LongitudinalMeasurement
from app.main import create_app


def measurement(measurement_id: str, metric: str, value: float, unit: str, date: str = "2026-10-01T00:00:00Z"):
    return LongitudinalMeasurement(measurement_id=measurement_id, metric=metric, value=value, unit=unit, observed_at=date, source_type="laboratory")


def request(disease_id: str, measurements: list[LongitudinalMeasurement]) -> ClinicalAssessmentRequest:
    return ClinicalAssessmentRequest(tenant_id="synthetic-phase1-tenant", patient_id="synthetic-phase1-patient", disease_id=disease_id, measurements=measurements, synthetic=True)


def test_normalization_converts_supported_units_without_mutating_source():
    source = measurement("g-1", "glucose", 6.0, "mmol/L")
    normalized = normalize_measurements([source])
    assert round(normalized[0].value, 1) == 108.1
    assert normalized[0].unit == "mg/dL"
    assert source.unit == "mmol/L"


def test_diabetes_vertical_slice_returns_gaps_and_draft_only_plan():
    result = assess(request("diabetes", [measurement("a1", "hba1c", 7.2, "%"), measurement("g1", "glucose", 130, "mg/dL")]), now=datetime(2026, 10, 10, tzinfo=timezone.utc))
    assert result.abstained is False
    assert result.follow_up_status == "REVIEW_REQUIRED"
    assert "renal_function" not in result.missing_metrics
    assert result.care_plan is not None and result.care_plan.draft_only is True
    assert "prescribe" in result.care_plan.blocked_actions
    assert result.clinical_use_authorized is False


def test_hypertension_requires_a_validated_bp_pair():
    result = assess(request("hypertension", [measurement("sys", "bp_systolic", 140, "mmHg")]), now=datetime(2026, 10, 10, tzinfo=timezone.utc))
    codes = {finding.code for finding in result.findings}
    assert "MISSING_REQUIRED_DATA" in codes
    assert "INCOMPLETE_BP_PAIR" in codes
    assert result.follow_up_status == "REVIEW_REQUIRED"


def test_ckd_flags_missing_uacr_and_retains_provenance():
    result = assess(request("chronic-kidney-disease", [measurement("e1", "egfr", 58, "mL/min/1.73m2")]), now=datetime(2026, 10, 10, tzinfo=timezone.utc))
    assert "urine_albumin" in result.missing_metrics
    assert any(f.code == "ALBUMINURIA_GAP" for f in result.findings)
    assert len(result.provenance.input_hash) == 64
    assert result.provenance.evidence_refs == ["e1"]


def test_unknown_pack_abstains_closed():
    result = assess(request("not-enabled", [measurement("x", "unknown", 1, "unit")]))
    assert result.abstained is True
    assert result.follow_up_status == "ABSTAINED"
    assert result.care_plan is None


def test_phase1_assessment_endpoint_is_synthetic_only_and_tenant_scoped():
    client = TestClient(create_app(Settings()))
    payload = {
        "tenant_id": "synthetic-api-tenant", "patient_id": "synthetic-api-patient", "disease_id": "diabetes", "synthetic": True,
        "measurements": [{"measurement_id": "a1", "metric": "hba1c", "value": 7.1, "unit": "%", "observed_at": "2026-10-01T00:00:00Z", "source_type": "laboratory"}],
    }
    response = client.post("/v1/disease-intelligence/clinical-assess", json=payload)
    assert response.status_code == 200
    assert response.json()["care_plan"]["clinician_approval_required"] is True
    denied = client.post("/v1/disease-intelligence/clinical-assess", json={**payload, "synthetic": False})
    assert denied.status_code == 403
