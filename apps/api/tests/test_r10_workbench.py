from __future__ import annotations

import pytest

from app.assessment_store import AssessmentConflict, AssessmentStore
from app.auth import GatewayPrincipal, make_test_token, verify_bearer_token
from app.config import Settings
from app.workbench import WorkbenchAccessContext, validate_workbench_access


def principal(*, patient_ids: frozenset[str] = frozenset({"synthetic-patient"}), purpose: str | None = "synthetic-evaluation", consent: str | None = "synthetic-consent") -> GatewayPrincipal:
    return GatewayPrincipal("clinician-1", "synthetic-tenant", patient_ids, frozenset({"clinical-workbench:read"}), frozenset({"clinician"}), "jti", purpose, consent, None)


def test_workbench_requires_purpose_consent_and_clinician_role():
    access = WorkbenchAccessContext(purpose_of_use="synthetic-evaluation", consent_id="synthetic-consent")
    validate_workbench_access(principal=principal(), access=access, tenant_id="synthetic-tenant", patient_id="synthetic-patient")
    with pytest.raises(PermissionError):
        validate_workbench_access(principal=principal(purpose=None), access=access, tenant_id="synthetic-tenant", patient_id="synthetic-patient")
    with pytest.raises(PermissionError):
        validate_workbench_access(principal=principal(patient_ids=frozenset({"synthetic-other"})), access=access, tenant_id="synthetic-tenant", patient_id="synthetic-patient")


def test_delegated_access_requires_matching_delegator():
    access = WorkbenchAccessContext(purpose_of_use="synthetic-evaluation", consent_id="synthetic-consent", delegated_access=True, delegated_by="supervisor-1")
    with pytest.raises(PermissionError):
        validate_workbench_access(principal=principal(), access=access, tenant_id="synthetic-tenant", patient_id="synthetic-patient")


def test_token_preserves_purpose_consent_and_delegation_claims():
    token = make_test_token("r10-secret", issuer="wyshcare", audience="wysh-ai", tenant_id="synthetic-tenant", patient_ids=["synthetic-patient"], scopes=["clinical-workbench:read"], roles=["clinician"], purpose_of_use="synthetic-evaluation", consent_id="synthetic-consent", delegated_by="supervisor-1")
    verified = verify_bearer_token(f"Bearer {token}", Settings(service_token_secret="r10-secret"), tenant_id="synthetic-tenant", patient_id="synthetic-patient", required_scope="clinical-workbench:read")
    assert verified.purpose_of_use == "synthetic-evaluation"
    assert verified.consent_id == "synthetic-consent"
    assert verified.delegated_by == "supervisor-1"


def test_approved_assessment_record_requires_persisted_approved_review_and_is_versioned():
    store = AssessmentStore(":memory:")
    draft = store.create_draft(tenant_id="synthetic-tenant", patient_id="synthetic-patient", evidence_hash="a" * 64, review_id="review-1")
    with pytest.raises(AssessmentConflict):
        store.approve_from_review(assessment_id=draft.assessment_id, tenant_id=draft.tenant_id, patient_id=draft.patient_id, review_id="review-1", review_state="DRAFT", actor="clinician-1", expected_version=1)
    approved = store.approve_from_review(assessment_id=draft.assessment_id, tenant_id=draft.tenant_id, patient_id=draft.patient_id, review_id="review-1", review_state="APPROVED", actor="clinician-1", expected_version=1)
    assert approved.state == "APPROVED"
    assert approved.version == 2
    with pytest.raises(AssessmentConflict):
        store.approve_from_review(assessment_id=draft.assessment_id, tenant_id=draft.tenant_id, patient_id=draft.patient_id, review_id="review-1", review_state="APPROVED", actor="clinician-1", expected_version=1)
