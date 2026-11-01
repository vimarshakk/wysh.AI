"""R9A/R9B synthetic imaging contracts and isolated adapter boundary.

The module accepts metadata and provenance only. It never reads image bytes or
invokes an imaging model from the API process. Adapters are research-only and
must return draft/abstain outputs with modality, model and input provenance.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import importlib.util
import json
import re
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, field_validator


class ImagingContractError(ValueError):
    pass


class SyntheticDicomMetadata(BaseModel):
    study_instance_uid: str = Field(min_length=8, max_length=128)
    series_instance_uid: str = Field(min_length=8, max_length=128)
    sop_instance_uid: str = Field(min_length=8, max_length=128)
    modality: Literal["CR", "DX", "CT", "MR", "US", "MG", "PT"]
    body_part: str = Field(min_length=1, max_length=100)
    transfer_syntax_uid: str = Field(min_length=3, max_length=64)
    pixel_hash: str = Field(min_length=64, max_length=64)
    de_identification_method: str = Field(min_length=1, max_length=200)
    synthetic: bool = True

    @field_validator("pixel_hash")
    @classmethod
    def hash_is_hex(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
            raise ValueError("pixel_hash must be a SHA-256 digest")
        return value.lower()

    @field_validator("synthetic")
    @classmethod
    def synthetic_required(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("R9 research contracts accept synthetic studies only")
        return value


class FhirImagingStudyContract(BaseModel):
    resource_type: Literal["ImagingStudy"] = "ImagingStudy"
    resource_id: str = Field(min_length=1, max_length=128)
    subject_reference: str = Field(min_length=1, max_length=200)
    status: Literal["available", "registered", "cancelled", "entered-in-error"]
    modality: Literal["CR", "DX", "CT", "MR", "US", "MG", "PT"]
    started: str = Field(min_length=10, max_length=64)
    dicom: SyntheticDicomMetadata
    synthetic: bool = True


class ImagingProvenanceRecord(BaseModel):
    contract_version: str = "r9a-imaging-contract-v1"
    source_hash: str = Field(min_length=64, max_length=64)
    fhir_resource_hash: str = Field(min_length=64, max_length=64)
    model_id: str = "unconfigured"
    model_version: str = "unavailable"
    license_status: Literal["NOT_APPLICABLE", "RESEARCH_ONLY", "VERIFIED"] = "NOT_APPLICABLE"
    de_identification_verified: bool = False


class ImagingAdapterRequest(BaseModel):
    study: FhirImagingStudyContract
    task: Literal["quality_check", "segmentation_draft", "report_draft"]
    provenance: ImagingProvenanceRecord


class ImagingAdapterResult(BaseModel):
    status: Literal["ABSTAINED", "DRAFT"] = "ABSTAINED"
    findings: list[str] = Field(default_factory=list)
    uncertainty: str = "No validated imaging model is configured."
    evidence_refs: list[str] = Field(default_factory=list)
    draft_only: bool = True
    clinical_use_authorized: bool = False


def canonical_source_hash(study: FhirImagingStudyContract) -> str:
    payload = study.model_dump(mode="json")
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_de_identification(study: FhirImagingStudyContract) -> dict[str, Any]:
    metadata = study.dicom
    checks = {
        "synthetic_marker": study.synthetic is True and metadata.synthetic is True,
        "de_identification_method_present": bool(metadata.de_identification_method.strip()),
        "subject_is_synthetic": study.subject_reference.startswith("Patient/synthetic-"),
        "uids_present": all(bool(value.strip()) for value in (metadata.study_instance_uid, metadata.series_instance_uid, metadata.sop_instance_uid)),
    }
    return {"status": "PASS" if all(checks.values()) else "ABSTAINED", "checks": checks}


class ImagingResearchAdapter(Protocol):
    adapter_id: str

    def analyze(self, request: ImagingAdapterRequest) -> ImagingAdapterResult: ...


@dataclass(frozen=True)
class UnconfiguredImagingAdapter:
    adapter_id: str = "unconfigured-imaging-adapter"

    def analyze(self, request: ImagingAdapterRequest) -> ImagingAdapterResult:
        return ImagingAdapterResult(uncertainty="Adapter unavailable; no model output was generated.")


@dataclass(frozen=True)
class MonaiResearchAdapter:
    adapter_id: str = "monai-research-adapter"
    model_id: str = "unconfigured-monai-model"

    @property
    def available(self) -> bool:
        return importlib.util.find_spec("monai") is not None

    def analyze(self, request: ImagingAdapterRequest) -> ImagingAdapterResult:
        if not self.available:
            return ImagingAdapterResult(uncertainty="MONAI is not installed; adapter remains unavailable and abstains.")
        return ImagingAdapterResult(uncertainty="MONAI adapter is present but no model weights or task configuration are approved.")


def adapter_status() -> list[dict[str, Any]]:
    monai = MonaiResearchAdapter()
    return [{"adapter_id": "unconfigured-imaging-adapter", "status": "AVAILABLE", "model_execution": "ABSTAIN"}, {"adapter_id": monai.adapter_id, "status": "AVAILABLE" if monai.available else "NOT_INSTALLED", "model_execution": "ABSTAIN"}]
