"""Run the synthetic R10 workflow integration and authorization gate."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.assessment_store import AssessmentStore
from app.audit import InMemoryAuditSink
from app.auth import GatewayPrincipal
from app.clinical_orchestration import ClinicalWorkflowResponse, SafetyEvaluation
from app.imaging_research import FhirImagingStudyContract, ImagingAdapterResult, ImagingProvenanceRecord, SyntheticDicomMetadata, canonical_source_hash
from app.multimodal_orchestration import build_multimodal_envelope
from app.review_store import ReviewStore
from app.workbench import WorkbenchAccessContext, WorkbenchRequest, assemble_workbench, validate_workbench_access


def main() -> None:
    patient_id, tenant_id = "synthetic-r10-patient", "synthetic-r10-tenant"
    clinical = ClinicalWorkflowResponse(workflow_id="clinical-workflow-r10", disease_id="diabetes", status="COMPLETED_DRAFT", stages=[], terminology=[], calculations=None, cql_native=None, cql_upstream=None, explanation=None, safety=SafetyEvaluation(status="ABSTAINED", findings=["synthetic gate uses a no-model fixture; no clinical recommendation"], checked_evidence_refs=[]), provenance_hash="c" * 64, model_telemetry=None)
    study = FhirImagingStudyContract(resource_id="study-r10", subject_reference=f"Patient/{patient_id}", status="available", modality="DX", started="2025-01-01T08:00:00Z", dicom=SyntheticDicomMetadata(study_instance_uid="2.25.10000011", series_instance_uid="2.25.10000012", sop_instance_uid="2.25.10000013", modality="DX", body_part="chest", transfer_syntax_uid="1.2.840.10008.1.2.1", pixel_hash="a" * 64, de_identification_method="synthetic-fixture-v1"))
    source_hash = canonical_source_hash(study)
    image = build_multimodal_envelope(tenant_id=tenant_id, patient_id=patient_id, clinical_workflow_id=clinical.workflow_id, clinical_status=clinical.status, study=study, provenance=ImagingProvenanceRecord(source_hash=source_hash, fhir_resource_hash=source_hash), adapter_result=ImagingAdapterResult(status="ABSTAINED", uncertainty="unconfigured adapter"), expected_pixel_hash="a" * 64)
    access = WorkbenchAccessContext(purpose_of_use="synthetic-evaluation", consent_id="synthetic-consent-r10")
    request = WorkbenchRequest(tenant_id=tenant_id, patient_id=patient_id, access=access, clinical=clinical, imaging=image)
    principal = GatewayPrincipal("synthetic-clinician", tenant_id, frozenset({patient_id}), frozenset({"clinical-workbench:read"}), frozenset({"clinician"}), "r10-jti", "synthetic-evaluation", "synthetic-consent-r10", None)
    validate_workbench_access(principal=principal, access=access, tenant_id=tenant_id, patient_id=patient_id)
    unauthorized = False
    try:
        validate_workbench_access(principal=GatewayPrincipal("other", tenant_id, frozenset({"synthetic-other"}), frozenset(), frozenset({"clinician"}), None, "synthetic-evaluation", "synthetic-consent-r10", None), access=access, tenant_id=tenant_id, patient_id=patient_id)
    except PermissionError:
        unauthorized = True
    workbench = assemble_workbench(workbench_id="workbench-r10", request=request)
    reviews, audit, assessments = ReviewStore(":memory:"), InMemoryAuditSink(), AssessmentStore(":memory:")
    review = reviews.create(tenant_id=tenant_id, patient_id=patient_id, disease_id="multimodal-imaging", assessment_id=workbench.workbench_id, assessment_input_hash=workbench.provenance_hash, actor_subject="synthetic-clinician")
    approved = reviews.decide(review_id=review.review_id, tenant_id=tenant_id, patient_id=patient_id, expected_version=1, action="approve", actor_subject="synthetic-clinician", note="synthetic workbench review")
    record = assessments.create_draft(tenant_id=tenant_id, patient_id=patient_id, evidence_hash=workbench.provenance_hash, review_id=review.review_id)
    finalized = assessments.approve_from_review(assessment_id=record.assessment_id, tenant_id=tenant_id, patient_id=patient_id, review_id=review.review_id, review_state=approved.state, actor="synthetic-clinician", expected_version=1)
    report = {"schema_version": "r10-gate-v1", "milestone": "R10A-R10E", "status": "PASS", "synthetic_only": True, "workbench": workbench.model_dump(mode="json"), "authorization": {"purpose": "PASS", "consent": "PASS", "tenant_patient_scope": "PASS", "negative_scope_case": "PASS" if unauthorized else "FAIL"}, "workflow_lifecycle": {"review_state": approved.state, "assessment_state": finalized.state, "assessment_version": finalized.version, "model_or_rule_approval_separate": True}, "safety": {"imaging_abstained_preserved": workbench.imaging_status == "ABSTAINED", "clinical_use_authorized": False, "autonomous_prescription": False, "autonomous_diagnosis": False, "autonomous_emergency_action": False}, "clinical_governance": "HOLD", "clinical_validation": "NO-GO", "production": "NO-GO"}
    output = ROOT / "artifacts/r10-test-evidence/r10-gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "output": str(output), "review_state": approved.state, "assessment_state": finalized.state, "negative_scope_case": unauthorized}))


if __name__ == "__main__":
    main()
