"""R12C parity and conformance contracts without adding external services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


class AuthorizationParityCase(BaseModel):
    case_id: str
    tenant_id: str
    patient_id: str
    relation: Literal["owner", "clinician", "caregiver", "ai-service", "none"]
    canonical_allowed: bool
    candidate_allowed: bool
    revoked: bool = False


def evaluate_authorization_parity(cases: list[AuthorizationParityCase]) -> dict[str, object]:
    mismatches = [case.case_id for case in cases if case.canonical_allowed != case.candidate_allowed or (case.revoked and case.candidate_allowed)]
    return {"status": "PASS" if not mismatches else "FAIL", "case_count": len(cases), "mismatches": mismatches, "candidate_is_reference_only": True}


class HapiConformanceContract(BaseModel):
    fhir_version: Literal["R4"] = "R4"
    required_resources: list[Literal["Bundle", "Patient", "Observation", "ImagingStudy", "Consent"]] = Field(min_length=1)
    terminology_validation_required: bool = True
    external_server_enabled: bool = False
    synthetic_only: Literal[True] = True


class TerminologyServiceContract(BaseModel):
    service: Literal["local", "snowstorm"] = "local"
    terminology_version: str = Field(min_length=1, max_length=100)
    code_systems: list[str] = Field(min_length=1)
    version_pinned: bool = True
    distribution_rights_reviewed: bool = False


@dataclass(frozen=True)
class AdapterDecision:
    project: str
    decision: str
    reason: str


def adapter_decisions() -> tuple[AdapterDecision, ...]:
    return (AdapterDecision("openfga/openfga", "REFERENCE_PARITY_ONLY", "canonical signed gateway policy remains authoritative"), AdapterDecision("hapifhir/hapi-fhir", "REFERENCE_CONFORMANCE_ONLY", "no second FHIR server enabled"), AdapterDecision("IHTSDO/snowstorm", "DEFERRED", "terminology distribution rights and operations not reviewed"))
