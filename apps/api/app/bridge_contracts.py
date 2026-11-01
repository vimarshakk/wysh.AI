"""Typed WyshCare ↔ wysh.AI bridge contract for synthetic integration tests."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BridgeEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=200)
    source_type: Literal["fhir_observation", "fhir_condition", "fhir_medication", "fhir_encounter", "clinical_document", "imaging_study"]
    recorded_at: str = Field(min_length=1, max_length=100)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class RequestedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=80)
    model_id: str = Field(min_length=1, max_length=200)
    model_version: str | None = Field(default=None, max_length=200)


class WyshCareAIBridgeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["wyshcare-ai-bridge-v1"] = "wyshcare-ai-bridge-v1"
    request_id: str = Field(min_length=1, max_length=128)
    correlation_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(pattern=r"^synthetic-.+", max_length=200)
    patient_id: str = Field(pattern=r"^synthetic-.+", max_length=200)
    practitioner_subject: str | None = Field(default=None, max_length=200)
    synthetic: Literal[True] = True
    purpose_of_use: str = Field(min_length=1, max_length=120)
    consent_id: str = Field(min_length=1, max_length=200)
    delegated_by: str | None = Field(default=None, max_length=200)
    evidence: list[BridgeEvidence] = Field(min_length=1, max_length=100)
    requested_model: RequestedModel
    requested_rule_version: str | None = Field(default=None, max_length=200)
    terminology_version: str | None = Field(default=None, max_length=200)
    review_required: Literal[True] = True
    clinical_use_authorized: Literal[False] = False

    @field_validator("purpose_of_use")
    @classmethod
    def purpose_is_explicit(cls, value: str) -> str:
        if value.lower() in {"", "unknown", "unspecified"}:
            raise ValueError("purpose of use must be explicit")
        return value


class WyshAIBridgeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["wyshcare-ai-bridge-v1"] = "wyshcare-ai-bridge-v1"
    request_id: str = Field(min_length=1, max_length=128)
    correlation_id: str = Field(min_length=1, max_length=128)
    status: Literal["COMPLETED_DRAFT", "ABSTAINED", "UNAVAILABLE"]
    reason: str = Field(min_length=1, max_length=300)
    model_id: str = Field(min_length=1, max_length=200)
    model_version: str | None = Field(default=None, max_length=200)
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    provenance_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    review_required: Literal[True] = True
    clinical_use_authorized: Literal[False] = False
    review_id: str | None = Field(default=None, max_length=200)
    review_version: int | None = Field(default=None, ge=1)

    @field_validator("evidence_refs")
    @classmethod
    def no_unknown_refs(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("duplicate evidence references are not permitted")
        return value
