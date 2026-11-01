from datetime import datetime, timezone  # noqa

from fastapi.testclient import TestClient

from app.auth import make_test_token
from app.config import Settings
from app.main import create_app
from app.rule_governance_store import RuleGovernanceStore


TENANT = "synthetic-r6b-tenant"


def token(secret: str, *, role: str, scopes: list[str], subject: str) -> str:
    return make_test_token(secret, issuer="wyshcare", audience="wysh-ai", tenant_id=TENANT, patient_ids=[], scopes=scopes, roles=[role], subject=subject)


def headers(value: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {value}"}


def create_body() -> dict:
    return {
        "tenant_id": TENANT,
        "rule_id": "diabetes.hypoglycemia-observation",
        "rule_version": "r6b-diabetes-hypoglycemia-v1",
        "disease_id": "diabetes",
        "evidence_id": "ada-soc-2026-hypoglycemia",
        "intended_use": "synthetic observation classification for clinician review",
        "revision_hash": "sha256:r6b-synthetic-revision",
        "expires_at": "2030-01-01T00:00:00Z",
        "synthetic": True,
    }


def transition_body(version: int, evidence: str = "ada-soc-2026-hypoglycemia") -> dict:
    return {"tenant_id": TENANT, "expected_version": version, "evidence_id": evidence, "synthetic": True}


def test_rule_lifecycle_requires_distinct_roles_and_preserves_patient_review_boundary():
    secret = "r6b-secret"
    app = create_app(Settings(service_token_secret=secret))
    app.state.rule_governance_store.close()
    app.state.rule_governance_store = RuleGovernanceStore(":memory:")
    client = TestClient(app)
    engineer = token(secret, role="rule-engineer", scopes=["clinical-rule:write", "clinical-rule:submit", "clinical-rule:approve", "clinical-rule:read"], subject="synthetic-engineer")
    reviewer = token(secret, role="clinical-reviewer", scopes=["clinical-rule:approve", "clinical-rule:read"], subject="synthetic-reviewer")
    governance = token(secret, role="clinical-governance", scopes=["clinical-rule:activate", "clinical-rule:revoke", "clinical-rule:read"], subject="synthetic-governance")

    created = client.post("/v1/clinical-rule-governance/rules", json=create_body(), headers=headers(engineer))
    assert created.status_code == 201
    assert created.json()["status"] == "DRAFT"
    submitted = client.post("/v1/clinical-rule-governance/rules/diabetes.hypoglycemia-observation/submit", json=transition_body(1), headers=headers(engineer))
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "REVIEWED"
    forged = client.post("/v1/clinical-rule-governance/rules/diabetes.hypoglycemia-observation/approve", json=transition_body(2), headers=headers(engineer))
    assert forged.status_code == 403
    approved = client.post("/v1/clinical-rule-governance/rules/diabetes.hypoglycemia-observation/approve", json=transition_body(2), headers=headers(reviewer))
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"
    active = client.post("/v1/clinical-rule-governance/rules/diabetes.hypoglycemia-observation/activate", json=transition_body(3), headers=headers(governance))
    assert active.status_code == 200
    assert active.json()["status"] == "ACTIVE"
    replay = client.post("/v1/clinical-rule-governance/rules/diabetes.hypoglycemia-observation/revoke", json=transition_body(3), headers=headers(governance))
    assert replay.status_code == 409
    revoked = client.post("/v1/clinical-rule-governance/rules/diabetes.hypoglycemia-observation/revoke", json=transition_body(4), headers=headers(governance))
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "REVOKED"
    assert {event["action"] for event in revoked.json()["events"]} == {"created", "submitted", "approved", "activated", "revoked"}


def test_rule_governance_binds_evidence_and_tenant():
    secret = "r6b-secret"
    app = create_app(Settings(service_token_secret=secret))
    app.state.rule_governance_store.close()
    app.state.rule_governance_store = RuleGovernanceStore(":memory:")
    client = TestClient(app)
    engineer = token(secret, role="rule-engineer", scopes=["clinical-rule:write", "clinical-rule:submit"], subject="synthetic-engineer")
    reviewer = token(secret, role="clinical-reviewer", scopes=["clinical-rule:approve"], subject="synthetic-reviewer")
    assert client.post("/v1/clinical-rule-governance/rules", json=create_body(), headers=headers(engineer)).status_code == 201
    assert client.post("/v1/clinical-rule-governance/rules/diabetes.hypoglycemia-observation/submit", json=transition_body(1), headers=headers(engineer)).status_code == 200
    mismatch = client.post("/v1/clinical-rule-governance/rules/diabetes.hypoglycemia-observation/approve", json=transition_body(2, "different-evidence"), headers=headers(reviewer))
    assert mismatch.status_code == 422
    other_tenant = make_test_token(secret, issuer="wyshcare", audience="wysh-ai", tenant_id="synthetic-other-tenant", patient_ids=[], scopes=["clinical-rule:read"], roles=["clinical-reviewer"], subject="synthetic-reviewer")
    denied = client.get("/v1/clinical-rule-governance/rules/diabetes.hypoglycemia-observation", params={"tenant_id": TENANT}, headers=headers(other_tenant))
    assert denied.status_code == 401


def test_expired_rule_cannot_be_approved():
    store = RuleGovernanceStore(":memory:")
    try:
        try:
            store.create(tenant_id=TENANT, rule_id="expired", rule_version="v1", disease_id="diabetes", evidence_id="e1", intended_use="synthetic", revision_hash="h", expires_at="2020-01-01T00:00:00Z", actor_subject="engineer")
        except ValueError:
            pass
        else:
            raise AssertionError("expired rule was accepted")
    finally:
        store.close()
