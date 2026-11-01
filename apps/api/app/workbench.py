"""R10 unified clinician workbench contracts and purpose-bound access policy."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .clinical_orchestration import ClinicalWorkflowResponse
from .multimodal_orchestration import MultimodalEvidenceEnvelope


class WorkbenchAccessContext(BaseModel):
    purpose_of_use: Literal["synthetic-evaluation"]
    consent_id: str = Field(min_length=1, max_length=200)
    delegated_access: bool = False
    delegated_by: str | None = Field(default=None, max_length=200)


class WorkbenchRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=200)
    patient_id: str = Field(min_length=1, max_length=200)
    access: WorkbenchAccessContext
    clinical: ClinicalWorkflowResponse
    imaging: MultimodalEvidenceEnvelope
    synthetic: Literal[True] = True


class WorkbenchResponse(BaseModel):
    workbench_id: str
    tenant_id: str
    patient_id: str
    clinical_status: str
    imaging_status: str
    imaging_findings: list[str]
    review_required: Literal[True] = True
    draft_only: Literal[True] = True
    clinical_use_authorized: Literal[False] = False
    authorization: WorkbenchAccessContext
    provenance_hash: str


def validate_workbench_access(*, principal: object, access: WorkbenchAccessContext, tenant_id: str, patient_id: str) -> None:
    if getattr(principal, "tenant_id", None) != tenant_id or patient_id not in getattr(principal, "patient_ids", frozenset()):
        raise PermissionError("patient or tenant scope denied")
    if getattr(principal, "purpose_of_use", None) != access.purpose_of_use or getattr(principal, "consent_id", None) != access.consent_id:
        raise PermissionError("purpose or consent boundary denied")
    if access.delegated_access and (not access.delegated_by or getattr(principal, "delegated_by", None) != access.delegated_by):
        raise PermissionError("delegated access boundary denied")
    if not getattr(principal, "roles", frozenset()).intersection({"clinician", "clinical-reviewer"}):
        raise PermissionError("clinician workbench role required")


def assemble_workbench(*, workbench_id: str, request: WorkbenchRequest) -> WorkbenchResponse:
    if request.imaging.patient_id != request.patient_id or request.imaging.tenant_id != request.tenant_id:
        raise PermissionError("multimodal evidence scope does not match workbench scope")
    return WorkbenchResponse(workbench_id=workbench_id, tenant_id=request.tenant_id, patient_id=request.patient_id, clinical_status=request.clinical.status, imaging_status=request.imaging.imaging.status, imaging_findings=request.imaging.imaging.findings, authorization=request.access, provenance_hash=request.imaging.provenance_hash)
