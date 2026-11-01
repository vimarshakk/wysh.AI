"""API contracts for the rule lifecycle; intentionally excludes patient data."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RuleCreateRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=200)
    rule_id: str = Field(min_length=1, max_length=200)
    rule_version: str = Field(min_length=1, max_length=100)
    disease_id: str = Field(min_length=1, max_length=100)
    evidence_id: str = Field(min_length=1, max_length=200)
    intended_use: str = Field(min_length=1, max_length=1000)
    revision_hash: str = Field(min_length=1, max_length=128)
    expires_at: str = Field(min_length=1, max_length=100)
    synthetic: Literal[True] = True


class RuleTransitionRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=200)
    expected_version: int = Field(ge=1)
    evidence_id: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=1000)
    synthetic: Literal[True] = True


class RuleEventResponse(BaseModel):
    event_id: str
    rule_id: str
    version: int
    action: str
    actor_subject: str
    actor_role: str
    evidence_id: str
    note: str | None
    occurred_at: str


class RuleGovernanceResponse(BaseModel):
    rule_id: str
    tenant_id: str
    rule_version: str
    disease_id: str
    evidence_id: str
    intended_use: str
    status: str
    version: int
    revision_hash: str
    created_at: str
    updated_at: str
    expires_at: str
    created_by: str
    approved_by: str | None
    approved_at: str | None
    events: list[RuleEventResponse]
