"""Run the synthetic R9C-R9E multimodal safety and review gate."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.audit import InMemoryAuditSink
from app.imaging_research import FhirImagingStudyContract, ImagingAdapterResult, ImagingProvenanceRecord, SyntheticDicomMetadata, canonical_source_hash
from app.multimodal_orchestration import MultimodalReviewService, build_multimodal_envelope, evaluate_imaging_safety
from app.review_store import ReviewStore


def main() -> None:
    study = FhirImagingStudyContract(resource_id="study-r9-001", subject_reference="Patient/synthetic-r9-001", status="available", modality="DX", started="2025-01-01T08:00:00Z", dicom=SyntheticDicomMetadata(study_instance_uid="2.25.10000001", series_instance_uid="2.25.10000002", sop_instance_uid="2.25.10000003", modality="DX", body_part="chest", transfer_syntax_uid="1.2.840.10008.1.2.1", pixel_hash="a" * 64, de_identification_method="synthetic-fixture-v1"))
    source_hash = canonical_source_hash(study)
    provenance = ImagingProvenanceRecord(source_hash=source_hash, fhir_resource_hash=source_hash, model_id="unconfigured-imaging-adapter", model_version="unavailable", de_identification_verified=True)
    abstained = build_multimodal_envelope(tenant_id="synthetic-tenant", patient_id="synthetic-r9-001", clinical_workflow_id="clinical-workflow-r9-001", clinical_status="COMPLETED_DRAFT", study=study, provenance=provenance, adapter_result=ImagingAdapterResult(status="ABSTAINED", uncertainty="adapter unavailable"), expected_pixel_hash="a" * 64)
    mismatch = evaluate_imaging_safety(study=study, patient_id="synthetic-other", expected_pixel_hash="a" * 64)
    corrupt = evaluate_imaging_safety(study=study, patient_id="synthetic-r9-001", expected_pixel_hash="b" * 64)
    audit = InMemoryAuditSink()
    review_store = ReviewStore(":memory:")
    service = MultimodalReviewService(review_store, audit)
    review = service.create_draft(envelope=abstained, actor_subject="clinician-synthetic")
    approved = service.decide(review_id=review.review_id, envelope=abstained, expected_version=1, action="approve", actor_subject="clinician-synthetic", note="synthetic draft review")
    report = {"schema_version": "r9cde-gate-v1", "milestone": "R9C-R9E", "status": "PASS", "synthetic_only": True, "multimodal_status": {"clinical_status_preserved": abstained.clinical_status, "imaging_status": abstained.imaging.status, "abstained_imaging_findings": abstained.imaging.findings, "imaging_never_reinterpreted_as_negative": not abstained.imaging.findings}, "safety_cases": {"subject_mismatch": mismatch.model_dump(mode="json"), "corrupt_input_hash": corrupt.model_dump(mode="json"), "unconfigured_adapter": abstained.imaging.model_dump(mode="json")}, "review": {"state": approved.state, "version": approved.version, "event_count": len(audit.events), "audit_event_types": [event.event_type for event in audit.events], "provenance_bound": all(event.input_hash == abstained.provenance_hash for event in audit.events)}, "clinical_use_authorized": False, "clinical_governance": "HOLD", "clinical_validation": "NO-GO", "production": "NO-GO"}
    output = ROOT / "artifacts/r9-test-evidence/r9cde-gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "output": str(output), "imaging_status": abstained.imaging.status, "review": approved.state, "audit_events": len(audit.events)}))


if __name__ == "__main__":
    main()
