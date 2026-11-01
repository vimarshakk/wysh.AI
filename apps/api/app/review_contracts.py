from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ClinicalReviewCreateRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    patient_id: str = Field(min_length=1, max_length=128)
    disease_id: str = Field(min_length=1, max_length=128)
    assessment_id: str = Field(min_length=1, max_length=128)
    assessment_input_hash: str = Field(min_length=16, max_length=256)
    synthetic: bool = True


class ClinicalReviewDecisionRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    patient_id: str = Field(min_length=1, max_length=128)
    expected_version: int = Field(ge=1)
    action: Literal["approve", "reject", "request_revision"]
    note: str | None = Field(default=None, max_length=2000)
    synthetic: bool = True


class ClinicalReviewEventResponse(BaseModel):
    event_id: str
    review_id: str
    version: int
    action: str
    actor_subject: str
    actor_role: str
    note: str | None
    occurred_at: str


class ClinicalReviewResponse(BaseModel):
    review_id: str
    tenant_id: str
    patient_id: str
    disease_id: str
    assessment_id: str
    assessment_input_hash: str
    state: str
    version: int
    created_at: str
    updated_at: str
    created_by: str
    latest_action: str
    events: list[ClinicalReviewEventResponse]
