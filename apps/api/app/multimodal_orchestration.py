"""R9C-R9E provenance, safety, and review envelope for synthetic multimodal work."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from .audit import InMemoryAuditSink, new_event
from .imaging_research import FhirImagingStudyContract, ImagingAdapterResult, ImagingProvenanceRecord, canonical_source_hash, validate_de_identification
from .review_store import ClinicalReview, ReviewConflict, ReviewNotFound, ReviewStore


class ImagingSafetyResult(BaseModel):
    status: Literal["PASS", "ABSTAINED"]
    reasons: list[str] = Field(default_factory=list)
    checks: dict[str, Literal["PASS", "FAIL", "NOT_CHECKED"]] = Field(default_factory=dict)


class ModalityEnvelope(BaseModel):
    modality: str
    status: Literal["DRAFT", "ABSTAINED", "UNAVAILABLE"]
    findings: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    source_hash: str
    model_id: str
    model_version: str
    uncertainty: str
    clinical_use_authorized: Literal[False] = False


class MultimodalEvidenceEnvelope(BaseModel):
    envelope_id: str
    tenant_id: str
    patient_id: str
    clinical_workflow_id: str
    clinical_status: str
    imaging: ModalityEnvelope
    imaging_safety: ImagingSafetyResult
    provenance_hash: str
    draft_only: Literal[True] = True
    review_required: Literal[True] = True
    clinical_use_authorized: Literal[False] = False


def _iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def evaluate_imaging_safety(*, study: FhirImagingStudyContract, patient_id: str, expected_pixel_hash: str | None = None, clinical_timestamps: list[str] | None = None) -> ImagingSafetyResult:
    checks: dict[str, Literal["PASS", "FAIL", "NOT_CHECKED"]] = {}
    reasons: list[str] = []
    deid = validate_de_identification(study)
    checks["de_identification_contract"] = "PASS" if deid["status"] == "PASS" else "FAIL"
    if checks["de_identification_contract"] == "FAIL":
        reasons.append("synthetic de-identification contract failed")
    checks["subject_consistency"] = "PASS" if study.subject_reference == f"Patient/{patient_id}" else "FAIL"
    if checks["subject_consistency"] == "FAIL":
        reasons.append("imaging subject does not match the workflow patient")
    if expected_pixel_hash is None:
        checks["pixel_integrity"] = "NOT_CHECKED"
    else:
        checks["pixel_integrity"] = "PASS" if expected_pixel_hash.lower() == study.dicom.pixel_hash else "FAIL"
        if checks["pixel_integrity"] == "FAIL":
            reasons.append("observed pixel hash does not match the registered study hash")
    started = _iso(study.started)
    if started is None:
        checks["timestamp_integrity"] = "FAIL"
        reasons.append("study timestamp is not valid ISO-8601")
    elif clinical_timestamps:
        parsed = [_iso(item) for item in clinical_timestamps]
        checks["timestamp_integrity"] = "PASS" if all(item is not None for item in parsed) else "FAIL"
        if checks["timestamp_integrity"] == "FAIL":
            reasons.append("clinical evidence contains an invalid timestamp")
    else:
        checks["timestamp_integrity"] = "NOT_CHECKED"
    return ImagingSafetyResult(status="PASS" if not reasons else "ABSTAINED", reasons=reasons, checks=checks)


def build_multimodal_envelope(*, tenant_id: str, patient_id: str, clinical_workflow_id: str, clinical_status: str, study: FhirImagingStudyContract, provenance: ImagingProvenanceRecord, adapter_result: ImagingAdapterResult, expected_pixel_hash: str | None = None, clinical_timestamps: list[str] | None = None) -> MultimodalEvidenceEnvelope:
    safety = evaluate_imaging_safety(study=study, patient_id=patient_id, expected_pixel_hash=expected_pixel_hash, clinical_timestamps=clinical_timestamps)
    safe = safety.status == "PASS"
    adapter_status = adapter_result.status if safe else "ABSTAINED"
    findings = adapter_result.findings if safe and adapter_status == "DRAFT" else []
    image = ModalityEnvelope(modality=study.modality, status=adapter_status, findings=findings, evidence_refs=adapter_result.evidence_refs if safe else [], source_hash=provenance.source_hash, model_id=provenance.model_id, model_version=provenance.model_version, uncertainty=adapter_result.uncertainty if safe else "; ".join(safety.reasons))
    digest = sha256(json.dumps({"clinical": clinical_workflow_id, "study": study.model_dump(mode="json"), "image": image.model_dump(mode="json"), "safety": safety.model_dump(mode="json")}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return MultimodalEvidenceEnvelope(envelope_id=f"multimodal-{digest[:24]}", tenant_id=tenant_id, patient_id=patient_id, clinical_workflow_id=clinical_workflow_id, clinical_status=clinical_status, imaging=image, imaging_safety=safety, provenance_hash=digest)


class MultimodalReviewService:
    """Binds a multimodal draft to the existing persistent review/audit boundary."""

    def __init__(self, review_store: ReviewStore, audit_sink: InMemoryAuditSink) -> None:
        self.review_store = review_store
        self.audit_sink = audit_sink

    def create_draft(self, *, envelope: MultimodalEvidenceEnvelope, actor_subject: str) -> ClinicalReview:
        review = self.review_store.create(tenant_id=envelope.tenant_id, patient_id=envelope.patient_id, disease_id="multimodal-imaging", assessment_id=envelope.envelope_id, assessment_input_hash=envelope.provenance_hash, actor_subject=actor_subject)
        self.audit_sink.append(new_event("clinical_review.created", envelope.envelope_id, envelope.tenant_id, envelope.patient_id, "draft", input_hash=envelope.provenance_hash, policy_version="r9e-multimodal-review-v1"))
        return review

    def decide(self, *, review_id: str, envelope: MultimodalEvidenceEnvelope, expected_version: int, action: Literal["approve", "reject", "request_revision"], actor_subject: str, note: str | None = None) -> ClinicalReview:
        review = self.review_store.decide(review_id=review_id, tenant_id=envelope.tenant_id, patient_id=envelope.patient_id, expected_version=expected_version, action=action, actor_subject=actor_subject, note=note)
        event_type = {"approve": "clinical_review.approved", "reject": "clinical_review.rejected", "request_revision": "clinical_review.revision_requested"}[action]
        self.audit_sink.append(new_event(event_type, envelope.envelope_id, envelope.tenant_id, envelope.patient_id, review.state.lower(), input_hash=envelope.provenance_hash, policy_version="r9e-multimodal-review-v1"))
        return review
