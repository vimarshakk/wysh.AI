from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth import make_test_token
from app.config import Settings
from app.main import create_app
from app.review_store import ReviewStore


TENANT = "synthetic-review-tenant"
PATIENT = "synthetic-review-patient"


def _client() -> tuple[TestClient, object, str]:
    app = create_app(Settings(service_token_secret="review-secret"))
    app.state.review_store.close()
    app.state.review_store = ReviewStore(":memory:")
    token = make_test_token(
        "review-secret", issuer="wyshcare", audience="wysh-ai", tenant_id=TENANT,
        patient_ids=[PATIENT], scopes=["clinical-review:read", "clinical-review:write"], roles=["clinician"], subject="clinician-42",
    )
    return TestClient(app), app, token


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create(client: TestClient, token: str) -> dict:
    response = client.post(
        "/v1/clinical-reviews", headers=_headers(token), json={
            "tenant_id": TENANT, "patient_id": PATIENT, "disease_id": "diabetes",
            "assessment_id": "assessment-1", "assessment_input_hash": "a" * 64, "synthetic": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_review_is_persisted_and_decision_history_is_immutable():
    client, app, token = _client()
    created = _create(client, token)
    assert created["state"] == "DRAFT"
    assert created["version"] == 1
    assert created["events"][0]["action"] == "created"

    approved = client.post(
        f"/v1/clinical-reviews/{created['review_id']}/decision", headers=_headers(token), json={
            "tenant_id": TENANT, "patient_id": PATIENT, "expected_version": 1,
            "action": "approve", "note": "Synthetic evidence reviewed.", "synthetic": True,
        },
    )
    assert approved.status_code == 200
    assert approved.json()["state"] == "APPROVED"
    assert approved.json()["version"] == 2
    assert [event["action"] for event in approved.json()["events"]] == ["created", "approve"]

    fetched = client.get(f"/v1/clinical-reviews/{created['review_id']}", params={"tenant_id": TENANT, "patient_id": PATIENT}, headers=_headers(token))
    assert fetched.status_code == 200
    assert fetched.json()["state"] == "APPROVED"
    assert len(fetched.json()["events"]) == 2

    stale = client.post(
        f"/v1/clinical-reviews/{created['review_id']}/decision", headers=_headers(token), json={
            "tenant_id": TENANT, "patient_id": PATIENT, "expected_version": 1,
            "action": "reject", "synthetic": True,
        },
    )
    assert stale.status_code == 409
    assert len(app.state.review_store.get(created["review_id"], tenant_id=TENANT, patient_id=PATIENT).events) == 2


def test_review_requires_clinician_role_and_scoped_bearer_token():
    client, _app, token = _client()
    assert client.post("/v1/clinical-reviews", json={"tenant_id": TENANT, "patient_id": PATIENT, "disease_id": "diabetes", "assessment_id": "assessment-1", "assessment_input_hash": "a" * 64, "synthetic": True}).status_code == 401

    non_clinician = make_test_token(
        "review-secret", issuer="wyshcare", audience="wysh-ai", tenant_id=TENANT,
        patient_ids=[PATIENT], scopes=["clinical-review:write"], roles=["care-navigator"],
    )
    denied = client.post("/v1/clinical-reviews", headers=_headers(non_clinician), json={"tenant_id": TENANT, "patient_id": PATIENT, "disease_id": "diabetes", "assessment_id": "assessment-1", "assessment_input_hash": "a" * 64, "synthetic": True})
    assert denied.status_code == 403

    wrong_patient = make_test_token(
        "review-secret", issuer="wyshcare", audience="wysh-ai", tenant_id=TENANT,
        patient_ids=["synthetic-other-patient"], scopes=["clinical-review:write"], roles=["clinician"],
    )
    assert client.post("/v1/clinical-reviews", headers=_headers(wrong_patient), json={"tenant_id": TENANT, "patient_id": PATIENT, "disease_id": "diabetes", "assessment_id": "assessment-1", "assessment_input_hash": "a" * 64, "synthetic": True}).status_code == 401

    parts = token.split(".")
    forged_signature = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
    forged = ".".join([parts[0], parts[1], forged_signature])
    assert client.post("/v1/clinical-reviews", headers=_headers(forged), json={"tenant_id": TENANT, "patient_id": PATIENT, "disease_id": "diabetes", "assessment_id": "assessment-1", "assessment_input_hash": "a" * 64, "synthetic": True}).status_code == 401


def test_review_replay_and_cross_tenant_reads_are_denied():
    client, _app, token = _client()
    created = _create(client, token)
    approved = client.post(f"/v1/clinical-reviews/{created['review_id']}/decision", headers=_headers(token), json={"tenant_id": TENANT, "patient_id": PATIENT, "expected_version": 1, "action": "approve", "synthetic": True})
    assert approved.status_code == 200
    replay = client.post(f"/v1/clinical-reviews/{created['review_id']}/decision", headers=_headers(token), json={"tenant_id": TENANT, "patient_id": PATIENT, "expected_version": 1, "action": "approve", "synthetic": True})
    assert replay.status_code == 409
    other_tenant = make_test_token("review-secret", issuer="wyshcare", audience="wysh-ai", tenant_id="synthetic-other-tenant", patient_ids=[PATIENT], scopes=["clinical-review:read"], roles=["clinician"])
    assert client.get(f"/v1/clinical-reviews/{created['review_id']}", params={"tenant_id": "synthetic-other-tenant", "patient_id": PATIENT}, headers=_headers(other_tenant)).status_code == 404


def test_revision_request_is_a_nonterminal_review_decision():
    client, _app, token = _client()
    created = _create(client, token)
    revised = client.post(
        f"/v1/clinical-reviews/{created['review_id']}/decision", headers=_headers(token), json={
            "tenant_id": TENANT, "patient_id": PATIENT, "expected_version": 1,
            "action": "request_revision", "note": "Add the missing renal observation.", "synthetic": True,
        },
    )
    assert revised.status_code == 200
    assert revised.json()["state"] == "REVISION_REQUESTED"
    assert revised.json()["version"] == 2
