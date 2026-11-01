"""Synthetic, deterministic evidence grounding shared by every application profile.

This is intentionally a bounded lexical retriever, not a clinical knowledge claim
or a replacement for an approved terminology/search service. It returns citations
and never generates an answer or persists source content.
"""

from __future__ import annotations

import re
from hashlib import sha256
import json
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class KnowledgeChunk(BaseModel):
    chunk_id: str = Field(min_length=1, max_length=200)
    source_id: str = Field(min_length=1, max_length=200)
    source_type: Literal["observation", "condition", "medication", "encounter", "document", "workflow"]
    recorded_at: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=4000)


class GroundingRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=200)
    patient_id: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=1000)
    chunks: list[KnowledgeChunk] = Field(min_length=1, max_length=50)
    top_k: int = Field(default=5, ge=1, le=10)
    synthetic: bool = False
    application_profile: Literal["patient-companion", "clinician-copilot", "care-navigation", "operations", "research"] = "clinician-copilot"

    @field_validator("chunks")
    @classmethod
    def unique_chunks(cls, value: list[KnowledgeChunk]) -> list[KnowledgeChunk]:
        ids = [item.chunk_id for item in value]
        if len(set(ids)) != len(ids):
            raise ValueError("chunk_id values must be unique")
        return value


class GroundingHit(BaseModel):
    chunk_id: str
    source_id: str
    source_type: str
    recorded_at: str
    title: str
    matched_terms: list[str]


class GroundingResponse(BaseModel):
    query_hash: str
    hits: list[GroundingHit]
    abstained: bool
    reason: str
    evidence_count: int
    synthetic_only: bool = True


def _terms(value: str) -> set[str]:
    return {term for term in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", value.lower()) if term not in {"the", "and", "for", "with", "which", "this"}}


def query_hash(request: GroundingRequest) -> str:
    canonical = request.model_dump(mode="json")
    return sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def ground(request: GroundingRequest) -> GroundingResponse:
    query_terms = _terms(request.question)
    ranked: list[tuple[int, KnowledgeChunk, list[str]]] = []
    for chunk in request.chunks:
        matched = sorted(query_terms & _terms(f"{chunk.title} {chunk.text}"))
        if matched:
            ranked.append((len(matched), chunk, matched))
    ranked.sort(key=lambda item: (-item[0], item[1].chunk_id))
    hits = [GroundingHit(chunk_id=chunk.chunk_id, source_id=chunk.source_id, source_type=chunk.source_type, recorded_at=chunk.recorded_at, title=chunk.title, matched_terms=matched) for _, chunk, matched in ranked[: request.top_k]]
    if not hits:
        return GroundingResponse(query_hash=query_hash(request), hits=[], abstained=True, reason="No typed evidence matched the query.", evidence_count=0)
    return GroundingResponse(query_hash=query_hash(request), hits=hits, abstained=False, reason="Evidence matches returned for human review.", evidence_count=len(hits))
