from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth import make_test_token
from app.config import Settings
from app.disease_specific_intelligence import DiseaseSpecificRequest, evaluate, load_disease_specific_packs
from app.disease_intelligence import LongitudinalMeasurement
from app.main import create_app


def m(mid: str, metric: str, value: float, unit: str, date: str = "2026-01-01T00:00:00Z") -> LongitudinalMeasurement:
    return LongitudinalMeasurement(measurement_id=mid, metric=metric, value=value, unit=unit, observed_at=date, source_type="laboratory")


def test_all_twenty_packs_have_condition_specific_observation_contracts():
    packs = load_disease_specific_packs()
    assert len(packs) == 20
    assert all(pack.schema_version == "r5c-disease-specific-v1" for pack in packs.values())
    assert all(pack.required_metrics for pack in packs.values())
    assert all(pack.unit_allowlist for pack in packs.values())


def test_wave_one_derived_metrics_and_trends_are_transparent():
    prediabetes = evaluate(DiseaseSpecificRequest(tenant_id="synthetic-t", patient_id="synthetic-p", disease_id="prediabetes", synthetic=True, measurements=[m("a1", "hba1c", 6.0, "%"), m("g1", "glucose", 110, "mg/dL"), m("g2", "glucose", 130, "mg/dL", "2026-02-01T00:00:00Z")]))
    assert prediabetes.status == "DATA_QUALITY_ONLY"
    assert next(item for item in prediabetes.derived_metrics if item.code == "A1C_TO_EAG").value == 125.5
    assert next(item for item in prediabetes.trends if item.metric == "glucose").direction == "UP"

    obesity = evaluate(DiseaseSpecificRequest(tenant_id="synthetic-t", patient_id="synthetic-p", disease_id="obesity", synthetic=True, measurements=[m("w", "weight", 80, "kg"), m("h", "height", 1.75, "m")]))
    assert next(item for item in obesity.derived_metrics if item.code == "BMI").value == 26.122
    dyslipidemia = evaluate(DiseaseSpecificRequest(tenant_id="synthetic-t", patient_id="synthetic-p", disease_id="dyslipidemia", synthetic=True, measurements=[m("tc", "total_cholesterol", 200, "mg/dL"), m("hdl", "hdl", 50, "mg/dL"), m("ldl", "ldl", 130, "mg/dL")]))
    assert next(item for item in dyslipidemia.derived_metrics if item.code == "NON_HDL").value == 150


def test_disease_specific_engine_abstains_on_unknown_or_invalid_units():
    unknown = evaluate(DiseaseSpecificRequest(tenant_id="synthetic-t", patient_id="synthetic-p", disease_id="unknown", synthetic=True, measurements=[m("x", "x", 1, "unit")]))
    assert unknown.status == "ABSTAINED"
    invalid = evaluate(DiseaseSpecificRequest(tenant_id="synthetic-t", patient_id="synthetic-p", disease_id="prediabetes", synthetic=True, measurements=[m("a", "hba1c", 6, "mg/dL"), m("g", "glucose", 120, "mg/dL")]))
    assert any(item.code == "UNIT_REVIEW_REQUIRED" for item in invalid.findings)
    assert invalid.status == "DATA_QUALITY_ONLY"


def test_disease_specific_endpoint_is_scoped_and_synthetic_only():
    app = create_app(Settings(service_token_secret="r5c-secret"))
    client = TestClient(app)
    token = make_test_token("r5c-secret", issuer="wyshcare", audience="wysh-ai", tenant_id="synthetic-t", patient_ids=["synthetic-p"], scopes=["disease:assess"])
    body = {"tenant_id": "synthetic-t", "patient_id": "synthetic-p", "disease_id": "prediabetes", "synthetic": True, "measurements": [m("a", "hba1c", 6, "%").model_dump(mode="json"), m("g", "glucose", 120, "mg/dL").model_dump(mode="json")]}
    response = client.post("/v1/disease-intelligence/disease-specific", json=body, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["status"] == "DATA_QUALITY_ONLY"
    body["synthetic"] = False
    assert client.post("/v1/disease-intelligence/disease-specific", json=body, headers={"Authorization": f"Bearer {token}"}).status_code == 403
