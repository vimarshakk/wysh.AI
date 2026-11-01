from fastapi.testclient import TestClient

from app.auth import make_test_token
from app.config import Settings
from app.main import create_app


def _request() -> dict:
    return {
        "request_id": "bridge-request-api-1",
        "correlation_id": "bridge-correlation-api-1",
        "tenant_id": "synthetic-tenant-1",
        "patient_id": "synthetic-patient-1",
        "practitioner_subject": "synthetic-clinician-1",
        "synthetic": True,
        "purpose_of_use": "synthetic-evaluation",
        "consent_id": "synthetic-consent-1",
        "evidence": [{"evidence_id": "obs-1", "source_type": "fhir_observation", "recorded_at": "2026-10-24T00:00:00Z", "content_sha256": "a" * 64}],
        "requested_model": {"provider": "medgemma", "model_id": "medgemma:latest", "model_version": "synthetic"},
        "requested_rule_version": "diabetes-r1",
        "terminology_version": "synthetic-terminology-v1",
        "review_required": True,
        "clinical_use_authorized": False,
    }


def test_bridge_returns_provenance_bound_abstention_without_authorizing_use():
    client = TestClient(create_app(Settings()))
    response = client.post("/v1/integration/wyshcare/clinical-draft", json=_request())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ABSTAINED"
    assert body["reason"] == "bridge contract validated; no clinical conclusion generated"
    assert body["evidence_refs"] == ["obs-1"]
    assert body["review_required"] is True
    assert body["clinical_use_authorized"] is False
    assert len(body["provenance_hash"]) == 64


def test_bridge_requires_gateway_auth_when_enabled():
    settings = Settings(require_gateway_auth=True, service_token_secret="test-secret")
    client = TestClient(create_app(settings))
    response = client.post("/v1/integration/wyshcare/clinical-draft", json=_request())
    assert response.status_code == 401


def test_bridge_gateway_auth_binds_purpose_consent_actor_and_role():
    secret = "bridge-auth-secret"
    settings = Settings(require_gateway_auth=True, service_token_secret=secret)
    client = TestClient(create_app(settings))
    token = make_test_token(
        secret,
        issuer="wyshcare",
        audience="wysh-ai",
        tenant_id="synthetic-tenant-1",
        patient_ids=["synthetic-patient-1"],
        scopes=["clinical-workflow:execute"],
        roles=["clinician"],
        subject="synthetic-clinician-1",
        purpose_of_use="synthetic-evaluation",
        consent_id="synthetic-consent-1",
    )
    response = client.post(
        "/v1/integration/wyshcare/clinical-draft",
        headers={"Authorization": f"Bearer {token}"},
        json=_request(),
    )
    assert response.status_code == 200
    assert response.json()["clinical_use_authorized"] is False

    wrong_purpose = make_test_token(
        secret,
        issuer="wyshcare",
        audience="wysh-ai",
        tenant_id="synthetic-tenant-1",
        patient_ids=["synthetic-patient-1"],
        scopes=["clinical-workflow:execute"],
        roles=["clinician"],
        subject="synthetic-clinician-1",
        purpose_of_use="different-purpose",
        consent_id="synthetic-consent-1",
    )
    denied = client.post(
        "/v1/integration/wyshcare/clinical-draft",
        headers={"Authorization": f"Bearer {wrong_purpose}"},
        json=_request(),
    )
    assert denied.status_code == 403


def test_bridge_gateway_auth_requires_exact_delegation_and_practitioner_binding():
    secret = "bridge-binding-secret"
    settings = Settings(require_gateway_auth=True, service_token_secret=secret)
    client = TestClient(create_app(settings))
    base_kwargs = {
        "issuer": "wyshcare",
        "audience": "wysh-ai",
        "tenant_id": "synthetic-tenant-1",
        "patient_ids": ["synthetic-patient-1"],
        "scopes": ["clinical-workflow:execute"],
        "roles": ["clinician"],
        "subject": "synthetic-clinician-1",
        "purpose_of_use": "synthetic-evaluation",
        "consent_id": "synthetic-consent-1",
    }
    delegated_token = make_test_token(secret, **base_kwargs, delegated_by="supervisor-1")
    assert client.post(
        "/v1/integration/wyshcare/clinical-draft",
        headers={"Authorization": f"Bearer {delegated_token}"},
        json=_request(),
    ).status_code == 403

    missing_actor = _request()
    missing_actor["practitioner_subject"] = None
    token = make_test_token(secret, **base_kwargs)
    assert client.post(
        "/v1/integration/wyshcare/clinical-draft",
        headers={"Authorization": f"Bearer {token}"},
        json=missing_actor,
    ).status_code == 403


def test_bridge_replay_is_idempotent_and_conflicting_content_is_rejected():
    client = TestClient(create_app(Settings()))
    first = client.post("/v1/integration/wyshcare/clinical-draft", headers={"Idempotency-Key": "bridge-idem-1"}, json=_request())
    replay = client.post("/v1/integration/wyshcare/clinical-draft", headers={"Idempotency-Key": "bridge-idem-1"}, json=_request())
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()

    conflicting = _request()
    conflicting["correlation_id"] = "different-content"
    response = client.post("/v1/integration/wyshcare/clinical-draft", headers={"Idempotency-Key": "bridge-idem-1"}, json=conflicting)
    assert response.status_code == 409


def test_bridge_is_disabled_outside_isolated_development():
    client = TestClient(create_app(Settings(environment="staging")))
    response = client.post("/v1/integration/wyshcare/clinical-draft", json=_request())
    assert response.status_code == 503
