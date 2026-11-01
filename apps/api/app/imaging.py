"""Validated imaging handoff contract with fail-closed analysis semantics."""

from __future__ import annotations

import re
from hashlib import sha256
import json
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ImagingStudy(BaseModel):
    study_id: str = Field(min_length=1, max_length=200)
    image_id: str = Field(min_length=1, max_length=200)
    modality: Literal["XR", "CT", "MR", "US", "PATHOLOGY"]
    content_type: Literal["image/dicom", "image/png", "image/jpeg", "image/tiff"]
    content_sha256: str = Field(min_length=64, max_length=64)
    width: int | None = Field(default=None, ge=1, le=100000)
    height: int | None = Field(default=None, ge=1, le=100000)
    synthetic: bool = False

    @field_validator("content_sha256")
    @classmethod
    def valid_sha256(cls, value: str) -> str:
        if not re.fullmatch(r"[a-fA-F0-9]{64}", value):
            raise ValueError("content_sha256 must be a SHA-256 hex digest")
        return value.lower()


class ImagingAnalysisRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=200)
    patient_id: str = Field(min_length=1, max_length=200)
    study: ImagingStudy
    task: Literal["quality_check", "segmentation_draft", "report_draft"]
    synthetic: bool = False
    application_profile: Literal["clinician-copilot", "research"] = "clinician-copilot"
    observations: list["ImagingObservation"] = Field(default_factory=list, max_length=20)
    segmentation_prompts: list["SegmentationPrompt"] = Field(default_factory=list, max_length=10)


class ImagingObservation(BaseModel):
    label: str = Field(min_length=1, max_length=300)
    body_region: str = Field(min_length=1, max_length=200)
    laterality: Literal["left", "right", "bilateral", "midline", "not-applicable", "unknown"] = "unknown"
    certainty: Literal["observed", "uncertain"] = "observed"
    evidence_ref: str = Field(min_length=1, max_length=200)


class SegmentationPrompt(BaseModel):
    prompt_type: Literal["point", "box", "scribble", "text"]
    coordinates: list[float] = Field(default_factory=list, max_length=128)
    text: str | None = Field(default=None, max_length=300)


class SegmentationJob(BaseModel):
    job_id: str
    status: Literal["QUEUED", "ABSTAINED"]
    prompt_count: int
    prompt_types: list[str]
    mask_references: list[str]


class ImagingQuality(BaseModel):
    passed: bool
    checks: dict[str, bool]
    reasons: list[str]


class ImagingWorkflowStep(BaseModel):
    tool_id: str
    purpose: str
    status: Literal["PLANNED", "COMPLETED", "ABSTAINED"]


class ImagingReportDraft(BaseModel):
    report_id: str
    technique: str
    findings: list[str]
    impression: str
    evidence_refs: list[str]
    draft_only: bool = True


class ImagingProvenance(BaseModel):
    input_hash: str
    policy_version: str
    model_id: str
    correlation_id: str


class ImagingAnalysisResponse(BaseModel):
    analysis_id: str
    status: Literal["ABSTAINED", "DRAFT"]
    task: str
    findings: list[str]
    mask_references: list[str]
    reason: str
    quality: ImagingQuality
    workflow: list[ImagingWorkflowStep]
    report: ImagingReportDraft | None = None
    segmentation: SegmentationJob | None = None
    provenance: ImagingProvenance
    human_review_required: bool = True
    clinical_use_authorized: bool = False


def imaging_input_hash(request: ImagingAnalysisRequest) -> str:
    return sha256(json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def assess_quality(study: ImagingStudy) -> ImagingQuality:
    checks = {
        "supported_modality": study.modality in {"XR", "CT", "MR", "US", "PATHOLOGY"},
        "content_hash_present": bool(study.content_sha256),
        "dimensions_present": study.width is not None and study.height is not None,
        "synthetic_marker_present": study.synthetic,
    }
    reasons = [name.replace("_", " ") for name, passed in checks.items() if not passed]
    return ImagingQuality(passed=all(checks.values()), checks=checks, reasons=reasons)


def plan_workflow(request: ImagingAnalysisRequest) -> list[ImagingWorkflowStep]:
    steps = [ImagingWorkflowStep(tool_id="image-quality-gate", purpose="Validate image metadata before any model call.", status="PLANNED")]
    if request.task == "segmentation_draft":
        steps.extend([
            ImagingWorkflowStep(tool_id="segmentation-adapter", purpose="Produce a clinician-editable mask draft through a separately validated adapter.", status="PLANNED"),
            ImagingWorkflowStep(tool_id="mask-provenance", purpose="Bind any future mask to the study hash, prompt, model, and reviewer.", status="PLANNED"),
        ])
    elif request.task == "report_draft":
        steps.extend([
            ImagingWorkflowStep(tool_id="vision-observation-adapter", purpose="Extract structured observations from an approved modality-specific model.", status="PLANNED"),
            ImagingWorkflowStep(tool_id="report-draft-composer", purpose="Compose a citation-linked draft for clinician review.", status="PLANNED"),
        ])
    return steps


def compose_report(request: ImagingAnalysisRequest) -> ImagingReportDraft | None:
    if request.task != "report_draft" or not request.observations:
        return None
    findings = []
    for observation in request.observations:
        side = "" if observation.laterality in {"unknown", "not-applicable"} else f" ({observation.laterality})"
        qualifier = "Uncertain: " if observation.certainty == "uncertain" else "Observed: "
        findings.append(f"{qualifier}{observation.label} in {observation.body_region}{side}.")
    return ImagingReportDraft(
        report_id=f"draft-{request.study.study_id}",
        technique=f"Synthetic {request.study.modality} study; metadata-only draft.",
        findings=findings,
        impression="Draft observations require clinician review; no diagnostic conclusion generated.",
        evidence_refs=[item.evidence_ref for item in request.observations],
    )


def compose_segmentation_job(request: ImagingAnalysisRequest) -> SegmentationJob | None:
    if request.task != "segmentation_draft":
        return None
    return SegmentationJob(
        job_id=f"seg-{request.study.study_id}",
        status="QUEUED" if request.segmentation_prompts else "ABSTAINED",
        prompt_count=len(request.segmentation_prompts),
        prompt_types=[item.prompt_type for item in request.segmentation_prompts],
        mask_references=[],
    )
