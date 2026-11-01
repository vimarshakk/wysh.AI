from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.assessment_store import AssessmentConflict, AssessmentStore
from app.auth import make_test_token
from app.config import Settings
from app.interoperability_contracts import SyntheticAbdmConsentContext, SyntheticAbdmExchange, validate_exchange_scope
from app.main import create_app
from app.review_store import ReviewConflict, ReviewStore
from app.workbench import WorkbenchAccessContext, validate_workbench_access
from app.auth import GatewayPrincipal


def principal(patient: str = "synthetic-patient", *, delegated_by: str | None = None) -> GatewayPrincipal:
    return GatewayPrincipal("clinician", "synthetic-tenant", frozenset({patient}), frozenset({"clinical-workbench:read"}), frozenset({"clinician"}), "jti", "synthetic-evaluation", "consent-1", delegated_by)


def bundle(patient: str = "synthetic-patient") -> dict:
    return {"resourceType": "Bundle", "meta": {"tag": [{"code": "synthetic"}]}, "entry": [{"resource": {"resourceType": "Patient", "id": patient}}]}


def test_cross_tenant_and_delegated_revocation_fail_closed():
    access = WorkbenchAccessContext(purpose_of_use="synthetic-evaluation", consent_id="consent-1", delegated_access=True, delegated_by="delegate-1")
    with pytest.raises(PermissionError):
        validate_workbench_access(principal=principal(), access=access, tenant_id="synthetic-tenant", patient_id="synthetic-patient")
    with pytest.raises(PermissionError):
        validate_workbench_access(principal=principal(delegated_by="delegate-1"), access=access, tenant_id="other-tenant", patient_id="synthetic-patient")


def test_stale_review_and_concurrent_decisions_are_rejected():
    store = ReviewStore(":memory:")
    review = store.create(tenant_id="synthetic-tenant", patient_id="synthetic-patient", disease_id="diabetes", assessment_id="a1", assessment_input_hash="a" * 64, actor_subject="clinician")
    approved = store.decide(review_id=review.review_id, tenant_id=review.tenant_id, patient_id=review.patient_id, expected_version=1, action="approve", actor_subject="clinician", note=None)
    assert approved.version == 2
    with pytest.raises(ReviewConflict):
        store.decide(review_id=review.review_id, tenant_id=review.tenant_id, patient_id=review.patient_id, expected_version=1, action="reject", actor_subject="clinician", note=None)


def test_assessment_replay_is_rejected_after_finalization():
    store = AssessmentStore(":memory:")
    record = store.create_draft(tenant_id="synthetic-tenant", patient_id="synthetic-patient", evidence_hash="a" * 64, review_id="review-1")
    store.approve_from_review(assessment_id=record.assessment_id, tenant_id=record.tenant_id, patient_id=record.patient_id, review_id="review-1", review_state="APPROVED", actor="clinician", expected_version=1)
    with pytest.raises(AssessmentConflict):
        store.approve_from_review(assessment_id=record.assessment_id, tenant_id=record.tenant_id, patient_id=record.patient_id, review_id="review-1", review_state="APPROVED", actor="clinician", expected_version=1)


def test_abdm_compatible_exchange_requires_granted_matching_synthetic_patient():
    consent = SyntheticAbdmConsentContext(consent_id="consent-1", purpose="synthetic-evaluation", hi_types=["Observation", "ImagingStudy"], patient_reference="Patient/synthetic-patient", requester_reference="Practitioner/synthetic-clinician")
    exchange = SyntheticAbdmExchange(consent=consent, fhir_bundle=bundle(), provenance_hash="b" * 64)
    assert validate_exchange_scope(exchange)["status"] == "PASS"
    revoked = exchange.model_copy(update={"consent": consent.model_copy(update={"status": "REVOKED"})})
    assert validate_exchange_scope(revoked)["status"] == "ABSTAINED"


def test_endpoint_rejects_cross_tenant_token_before_workbench_assembly():
    from app.workbench import WorkbenchRequest  # noqa
    token = make_test_token("r11-secret", issuer="wyshcare", audience="wysh-ai", tenant_id="other-tenant", patient_ids=["synthetic-other"], scopes=["clinical-workbench:read"], roles=["clinician"], purpose_of_use="synthetic-evaluation", consent_id="consent-1")
    app = create_app(Settings(service_token_secret="r11-secret"))
    client = TestClient(app)
    payload = {"tenant_id": "synthetic-tenant", "patient_id": "synthetic-patient", "access": {"purpose_of_use": "synthetic-evaluation", "consent_id": "consent-1"}, "clinical": {"workflow_id": "w", "disease_id": "diabetes", "status": "ABSTAINED", "stages": [], "terminology": [], "calculations": None, "cql_native": None, "cql_upstream": None, "explanation": None, "safety": {"status": "ABSTAINED", "findings": [], "checked_evidence_refs": []}, "provenance_hash": "c" * 64}, "imaging": {"envelope_id": "e", "tenant_id": "synthetic-tenant", "patient_id": "synthetic-patient", "clinical_workflow_id": "w", "clinical_status": "ABSTAINED", "imaging": {"modality": "DX", "status": "ABSTAINED", "findings": [], "evidence_refs": [], "source_hash": "a" * 64, "model_id": "unconfigured", "model_version": "unavailable", "uncertainty": "none"}, "imaging_safety": {"status": "ABSTAINED", "reasons": [], "checks": {}}, "provenance_hash": "d" * 64}}  # noqa
    assert client.post("/v1/clinical-workbench/synthetic", json=payload, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_authorization_check_is_stable_under_concurrency():
    access = WorkbenchAccessContext(purpose_of_use="synthetic-evaluation", consent_id="consent-1")
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: validate_workbench_access(principal=principal(), access=access, tenant_id="synthetic-tenant", patient_id="synthetic-patient"), range(32)))
    assert len(results) == 32
