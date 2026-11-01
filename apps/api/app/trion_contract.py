from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .schemas import ClinicalFact


class TrionFhirDraftRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=200)
    patient_id: str = Field(min_length=1, max_length=200)
    document_id: str = Field(min_length=1, max_length=200)
    practitioner_subject: str | None = Field(default=None, max_length=200)
    purpose_of_use: str | None = Field(default=None, max_length=120)
    consent_id: str | None = Field(default=None, max_length=200)
    delegated_by: str | None = Field(default=None, max_length=200)
    synthetic: bool = False
    facts: list[ClinicalFact] = Field(min_length=1, max_length=100)


class FhirDraftResource(BaseModel):
    draftResourceType: str = Field(min_length=1, max_length=100)
    assertionMode: Literal["DRAFT", "SUGGESTED"]
    payload: dict


class TrionFhirDraftResponse(BaseModel):
    schemaVersion: Literal[1]
    documentId: str
    resources: list[FhirDraftResource]
    generatedBy: Literal["TRION"]
    model: str | None = None
