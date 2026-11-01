from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import make_test_token
from app.config import Settings
from app.main import create_app
from app.verified_calculations import CalculationRequest, calculate


def measurement(measurement_id: str, metric: str, value: float, unit: str, observed_at: str = "2026-01-01T00:00:00Z") -> dict:
    return {"measurement_id": measurement_id, "metric": metric, "value": value, "unit": unit, "observed_at": observed_at, "source_type": "laboratory"}


def test_reference_vectors_are_reproducible():
    root = Path(__file__).parents[3]
    vectors = json.loads((root / "fixtures/synthetic/clinical-calculations/r4b-reference-vectors.json").read_text())
    diabetes = calculate(CalculationRequest(tenant_id="synthetic-t", patient_id="synthetic-p", disease_id="diabetes", synthetic=True, measurements=[measurement("a1c", "hba1c", 7.0, "%")]))
    assert diabetes.calculations[0].value == vectors["vectors"][0]["expected"]["value"]

    bp = calculate(CalculationRequest(tenant_id="synthetic-t", patient_id="synthetic-p", disease_id="hypertension", synthetic=True, measurements=[measurement("s1", "bp_systolic", 120, "mmHg"), measurement("d1", "bp_diastolic", 80, "mmHg"), measurement("s2", "bp_systolic", 130, "mmHg", "2026-01-02T00:00:00Z"), measurement("d2", "bp_diastolic", 85, "mmHg", "2026-01-02T00:00:00Z")]))
    assert next(item for item in bp.calculations if item.code == "MEAN_PULSE_PRESSURE").value == vectors["vectors"][1]["expected"]["value"]

    ckd = calculate(CalculationRequest(tenant_id="synthetic-t", patient_id="synthetic-p", disease_id="chronic-kidney-disease", age_years=60, sex="male", synthetic=True, measurements=[measurement("cr", "creatinine", 1.0, "mg/dL")]))
    result = next(item for item in ckd.calculations if item.code == "EGFR_CKD_EPI_2021")
    assert abs((result.value or 0) - vectors["vectors"][2]["expected"]["value"]) <= vectors["vectors"][2]["expected"]["tolerance"]


def test_ckd_abstains_without_demographics_and_no_clinical_thresholds_are_returned():
    result = calculate(CalculationRequest(tenant_id="synthetic-t", patient_id="synthetic-p", disease_id="chronic-kidney-disease", synthetic=True, measurements=[measurement("cr", "creatinine", 1.0, "mg/dL")]))
    assert result.abstained is False
    assert result.calculations[0].status == "ABSTAINED"
    assert result.calculations[0].value is None
    assert "treatment instruction" not in result.calculations[0].limitation.lower()


def test_calculations_fail_closed_for_invalid_domains_and_age_is_adult_only():
    invalid = calculate(CalculationRequest(tenant_id="synthetic-t", patient_id="synthetic-p", disease_id="diabetes", synthetic=True, measurements=[measurement("g", "glucose", -1, "mg/dL")]))
    assert invalid.abstained is True
    assert invalid.calculations[0].code == "INVALID_NUMERIC_INPUT"
    try:
        CalculationRequest(tenant_id="synthetic-t", patient_id="synthetic-p", disease_id="chronic-kidney-disease", age_years=17, sex="male", synthetic=True, measurements=[measurement("cr", "creatinine", 1.0, "mg/dL")])
    except ValueError:
        pass
    else:
        raise AssertionError("CKD-EPI request must reject pediatric age in the adult calculator")


def test_calculation_endpoint_requires_scope_and_is_synthetic_only():
    app = create_app(Settings(service_token_secret="calc-secret"))
    client = TestClient(app)
    token = make_test_token("calc-secret", issuer="wyshcare", audience="wysh-ai", tenant_id="synthetic-t", patient_ids=["synthetic-p"], scopes=["disease:calculate"])
    body = {"tenant_id": "synthetic-t", "patient_id": "synthetic-p", "disease_id": "diabetes", "synthetic": True, "measurements": [measurement("g", "glucose", 120, "mg/dL")]}
    assert client.post("/v1/disease-intelligence/verified-calculations", json=body).status_code == 200
    assert client.post("/v1/disease-intelligence/verified-calculations", json=body, headers={"Authorization": f"Bearer {token}"}).status_code == 200
    body["synthetic"] = False
    assert client.post("/v1/disease-intelligence/verified-calculations", json=body, headers={"Authorization": f"Bearer {token}"}).status_code == 403
