from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field

class Evidence(BaseModel):
    source_id: str = Field(min_length=1)
    source_type: Literal["observation", "condition", "medication", "encounter", "document"]
    recorded_at: str

class ClinicalFact(BaseModel):
    statement: str = Field(min_length=1, max_length=2000)
    evidence: list[Evidence] = Field(min_length=1)

class SnapshotRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    patient_id: str = Field(min_length=1)
    synthetic: bool = False
    facts: list[ClinicalFact] = Field(default_factory=list, max_length=100)

class ReviewState(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class SnapshotResponse(BaseModel):
    snapshot_id: str
    patient_id: str
    tenant_id: str
    state: ReviewState = ReviewState.DRAFT
    facts: list[ClinicalFact]
    summary: str
    model_id: str
    human_review_required: bool = True
    clinical_use_authorized: bool = False
