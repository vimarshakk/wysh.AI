from __future__ import annotations

from app.audit import InMemoryAuditSink
from app.imaging_research import FhirImagingStudyContract, ImagingAdapterResult, ImagingProvenanceRecord, SyntheticDicomMetadata
from app.multimodal_orchestration import MultimodalReviewService, build_multimodal_envelope, evaluate_imaging_safety
from app.review_store import ReviewStore


def study(subject: str = "Patient/synthetic-mm-001") -> FhirImagingStudyContract:
    return FhirImagingStudyContract(resource_id="study-mm-001", subject_reference=subject, status="available", modality="DX", started="2025-01-01T08:00:00Z", dicom=SyntheticDicomMetadata(study_instance_uid="2.25.10000001", series_instance_uid="2.25.10000002", sop_instance_uid="2.25.10000003", modality="DX", body_part="chest", transfer_syntax_uid="1.2.840.10008.1.2.1", pixel_hash="a" * 64, de_identification_method="synthetic-fixture-v1"))


def envelope(subject: str = "Patient/synthetic-mm-001", result: ImagingAdapterResult | None = None):
    current = study(subject)
    provenance = ImagingProvenanceRecord(source_hash="a" * 64, fhir_resource_hash="b" * 64, model_id="test-adapter", model_version="test-v1", license_status="RESEARCH_ONLY", de_identification_verified=True)
    return build_multimodal_envelope(tenant_id="synthetic-tenant", patient_id="synthetic-mm-001", clinical_workflow_id="clinical-workflow-001", clinical_status="COMPLETED_DRAFT", study=current, provenance=provenance, adapter_result=result or ImagingAdapterResult(status="ABSTAINED", findings=["must not become a negative imaging finding"]), expected_pixel_hash="a" * 64)


def test_abstained_imaging_is_unavailable_not_negative():
    result = envelope()
    assert result.imaging.status == "ABSTAINED"
    assert result.imaging.findings == []
    assert result.clinical_use_authorized is False


def test_mismatched_subject_and_corrupt_hash_fail_closed():
    mismatch = envelope("Patient/synthetic-other")
    assert mismatch.imaging_safety.status == "ABSTAINED"
    corrupt = evaluate_imaging_safety(study=study(), patient_id="synthetic-mm-001", expected_pixel_hash="b" * 64)
    assert corrupt.status == "ABSTAINED"
    assert corrupt.checks["pixel_integrity"] == "FAIL"


def test_draft_is_persisted_and_review_events_are_immutable_audit_records():
    store, audit = ReviewStore(":memory:"), InMemoryAuditSink()
    service = MultimodalReviewService(store, audit)
    draft = envelope(result=ImagingAdapterResult(status="DRAFT", findings=["synthetic research observation"], evidence_refs=["img:1"], uncertainty="research-only"))
    review = service.create_draft(envelope=draft, actor_subject="clinician-synthetic")
    approved = service.decide(review_id=review.review_id, envelope=draft, expected_version=1, action="approve", actor_subject="clinician-synthetic", note="reviewed synthetic draft")
    assert approved.state == "APPROVED"
    assert [event.event_type for event in audit.events] == ["clinical_review.created", "clinical_review.approved"]
    assert audit.events[1].input_hash == draft.provenance_hash
