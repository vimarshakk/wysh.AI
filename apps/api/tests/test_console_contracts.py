from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_console_exposes_only_synthetic_patient_summaries_and_cases():
    client = TestClient(create_app(Settings()))
    index = client.get("/v1/console/synthetic-patients")
    assert index.status_code == 200
    body = index.json()
    assert body["synthetic_only"] is True
    assert len(body["patients"]) == 60
    assert all(item["synthetic"] is True for item in body["patients"])
    case = client.get("/v1/console/synthetic-patients/diabetes-01")
    assert case.status_code == 200
    assert case.json()["measurements"]
    missing = client.get("/v1/console/synthetic-patients/not-a-case")
    assert missing.status_code == 404


def test_console_evaluation_status_is_evidence_backed_and_not_release_ready():
    client = TestClient(create_app(Settings()))
    response = client.get("/v1/console/evaluation-status")
    assert response.status_code == 200
    body = response.json()
    assert body["wdi_program_status"] == "IN_PROGRESS"
    assert body["phase1_evaluation"] == "PASS"
    assert body["clinical_validation"] == "NOT_STARTED"
    assert body["external_connectivity"] == "DEFERRED"


def test_console_local_cors_is_limited_to_development_origins():
    client = TestClient(create_app(Settings()))
    allowed = client.options("/v1/console/synthetic-patients", headers={"Origin": "http://127.0.0.1:3000", "Access-Control-Request-Method": "GET"})
    assert allowed.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"
    denied = client.options("/v1/console/synthetic-patients", headers={"Origin": "https://example.invalid", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in denied.headers
