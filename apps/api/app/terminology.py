"""Versioned terminology-provider contract with synthetic, non-licensed content."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


TERMINOLOGY_VERSION = "wysh.synthetic.terminology.v1"


class TerminologyValidationRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=200)
    system: str = Field(min_length=1, max_length=300)
    code: str = Field(min_length=1, max_length=100)
    display: str | None = Field(default=None, max_length=300)
    value_set_url: str | None = Field(default=None, max_length=500)
    synthetic: bool = False


class TerminologyValidationResponse(BaseModel):
    provider: Literal["wysh-synthetic-terminology"] = "wysh-synthetic-terminology"
    terminology_version: str = TERMINOLOGY_VERSION
    status: Literal["VALID", "NOT_FOUND", "ABSTAINED"]
    system: str
    code: str
    value_set_url: str | None
    reason: str
    clinical_use_authorized: Literal[False] = False
    synthetic_only: Literal[True] = True


_CODES = {
    ("http://loinc.org", "2339-0"): "Glucose [Mass/volume] in Blood",
    ("http://loinc.org", "4548-4"): "Hemoglobin A1c/Hemoglobin.total in Blood",
}


def validate_code(request: TerminologyValidationRequest) -> TerminologyValidationResponse:
    if request.value_set_url not in {None, "https://wysh.ai/fhir/ValueSet/synthetic-diabetes-observations"}:
        return TerminologyValidationResponse(status="ABSTAINED", system=request.system, code=request.code, value_set_url=request.value_set_url, reason="Only the versioned synthetic ValueSet contract is configured; no external terminology service was queried.")
    expected = _CODES.get((request.system, request.code))
    if expected is None:
        return TerminologyValidationResponse(status="NOT_FOUND", system=request.system, code=request.code, value_set_url=request.value_set_url, reason="Code is not present in the synthetic terminology registry; no clinical interpretation was attempted.")
    if request.display and request.display != expected:
        return TerminologyValidationResponse(status="ABSTAINED", system=request.system, code=request.code, value_set_url=request.value_set_url, reason="Display text does not match the versioned synthetic terminology entry.")
    return TerminologyValidationResponse(status="VALID", system=request.system, code=request.code, value_set_url=request.value_set_url, reason="Code matched the versioned synthetic terminology registry.")
