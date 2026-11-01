from __future__ import annotations

import re
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class EvidenceReference(BaseModel):
    source_id: str = Field(min_length=1, max_length=200)
    source_type: Literal["observation", "condition", "medication", "encounter", "document", "workflow"]
    recorded_at: str = Field(min_length=1, max_length=100)
    locator: str | None = Field(default=None, max_length=500)


class DecisionProvenance(BaseModel):
    generated_at: str
    input_hash: str
    model_id: str
    policy_version: str
    correlation_id: str
    evidence_count: int = Field(ge=0)


class DecisionRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=200)
    patient_id: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=1000)
    permitted_options: list[str] = Field(min_length=2, max_length=20)
    context: dict[str, str | int | float | bool | None] = Field(default_factory=dict, max_length=20)
    evidence_refs: list[str] = Field(default_factory=list, max_length=50)
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=50)
    synthetic: bool = False
    provider: str = "auto"
    application_profile: Literal["clinician-copilot", "care-navigation", "operations"] = "clinician-copilot"

    @field_validator("permitted_options")
    @classmethod
    def options_are_unique(cls, value: list[str]) -> list[str]:
        if len({item.strip() for item in value}) != len(value):
            raise ValueError("permitted_options must be unique")
        return value

    @field_validator("evidence")
    @classmethod
    def evidence_is_unique(cls, value: list[EvidenceReference]) -> list[EvidenceReference]:
        ids = [item.source_id for item in value]
        if len(set(ids)) != len(ids):
            raise ValueError("evidence source_id values must be unique")
        return value

    @field_validator("context")
    @classmethod
    def context_is_bounded_metadata(cls, value: dict[str, str | int | float | bool | None]) -> dict[str, str | int | float | bool | None]:
        if any(isinstance(item, str) and len(item) > 500 for item in value.values()):
            raise ValueError("context values are bounded workflow metadata; raw documents are not accepted")
        return value


class DecisionRouteAttempt(BaseModel):
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=200)
    status: Literal["skipped", "failure", "success"]
    reason: str | None = Field(default=None, max_length=80)
    latency_ms: int = Field(default=0, ge=0)


class DecisionResponse(BaseModel):
    decision_id: str
    selected_option: str | None
    rationale: str
    abstained: bool
    confidence: float | None = Field(default=None, ge=0, le=1)
    model_id: str
    policy_version: str
    evidence_refs: list[str]
    evidence: list[EvidenceReference]
    provenance: DecisionProvenance
    telemetry: "DecisionTelemetry | None" = None
    human_review_required: bool = True
    clinical_use_authorized: bool = False


class DecisionTelemetry(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=200)
    status: Literal["policy_abstained", "inference_success"]
    latency_ms: int = Field(ge=0)
    schema_validated: bool
    route_attempts: list[DecisionRouteAttempt] = Field(default_factory=list, max_length=10)
    retry_count: int = Field(default=0, ge=0, le=5)


class DecisionModelOutput(BaseModel):
    selected_option: str | None
    rationale: str = Field(min_length=1, max_length=2000)
    abstained: bool
    confidence: float | None = Field(default=None, ge=0, le=1)


_UNSAFE_OUTPUT_LANGUAGE = re.compile(
    r"\b(?:diagnos(?:e|is|ed|ing)|prescrib(?:e|ed|ing)|medication|treatment|emergency|"
    r"take|start|stop|increase|decrease|change\s+(?:the\s+)?dose)\b",
    re.I,
)
_OUTPUT_INJECTION_LANGUAGE = re.compile(r"\b(?:ignore\s+(?:all|any|the)\s+previous|system\s+prompt|developer\s+message|reveal\s+hidden|override\s+safety)\b", re.I)


def policy_check(request: DecisionRequest) -> None:
    if not request.synthetic:
        raise ValueError("decision service accepts synthetic requests only")
    if not request.tenant_id.startswith("synthetic-") or not request.patient_id.startswith("synthetic-"):
        raise ValueError("decision service accepts synthetic tenant and patient identifiers only")
    if re.search(r"diagnos|prescrib|medication|treatment|triage|emergency", request.question, re.I):
        raise ValueError("clinical decision categories are outside this non-diagnostic R1 policy")
    forbidden_context_keys = {"name", "full_name", "email", "phone", "mobile", "address", "dob", "date_of_birth", "aadhaar", "mrn", "medical_record_number", "ssn", "free_text", "document"}
    if forbidden_context_keys.intersection(key.lower() for key in request.context):
        raise ValueError("decision context contains a prohibited identifier or raw-text field")
    serialized_context = json.dumps(request.context, sort_keys=True)
    if re.search(r"(?:\b\d{10}\b|\b\d{12}\b|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})", serialized_context):
        raise ValueError("decision context contains a prohibited identifier pattern")


def validate_output(output: DecisionModelOutput, request: DecisionRequest) -> DecisionModelOutput:
    if _UNSAFE_OUTPUT_LANGUAGE.search(output.rationale) or _OUTPUT_INJECTION_LANGUAGE.search(output.rationale):
        return DecisionModelOutput(
            selected_option=None,
            rationale="Abstained because the generated text crossed the non-diagnostic safety boundary.",
            abstained=True,
            confidence=None,
        )
    if output.abstained:
        return output.model_copy(update={"selected_option": None, "confidence": None})
    if not request.evidence:
        return output.model_copy(update={"selected_option": None, "abstained": True, "confidence": None, "rationale": "Abstained because no typed supporting evidence was supplied."})
    if output.selected_option not in request.permitted_options:
        return output.model_copy(update={"selected_option": None, "abstained": True, "confidence": None, "rationale": "Abstained because the selected option was not permitted."})
    return output.model_copy(update={"confidence": None})


def input_hash(request: DecisionRequest) -> str:
    canonical = {
        "tenant_id": request.tenant_id,
        "patient_id": request.patient_id,
        "question": request.question,
        "application_profile": request.application_profile,
        "provider": request.provider,
        "permitted_options": request.permitted_options,
        "context": request.context,
        "evidence_refs": request.evidence_refs,
        "evidence": [item.model_dump(mode="json") for item in request.evidence],
    }
    return sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def generated_at() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
