"""System One clinical safety reviewer panel.

Phase 2 prototype. Interface for qualified clinical safety reviewers to review,
adjudicate, and sign off on model outputs. Every reviewer action is recorded
as an immutable audit record. Reviewer sign-off is required before any model
output can be considered for clinical use; no reviewer action grants
CLINICALLY_APPROVED status automatically.

Synthetic-only: reviewers evaluate de-identified synthetic cases. Real patient
data requires separate consent, de-identification, and governance approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ReviewerError(ValueError):
    pass


ReviewerRole = Literal["clinician-safety", "clinical-lead", "regulatory", "ethics"]
ReviewDecision = Literal["APPROVE", "REJECT", "ABSTAIN", "REQUEST_REVISION"]


class ReviewerIdentity(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    role: ReviewerRole
    qualifications: str = Field(min_length=1, max_length=1000)
    conflict_of_interest: str = Field(default="", max_length=1000)


class ReviewRecord(BaseModel):
    record_id: str = Field(min_length=1, max_length=200)
    case_id: str = Field(min_length=1, max_length=200)
    model_id: str = Field(min_length=1, max_length=200)
    reviewer_id: str = Field(min_length=1, max_length=200)
    reviewer_role: ReviewerRole
    decision: ReviewDecision
    rationale: str = Field(min_length=1, max_length=2000)
    confidence_in_decision: float = Field(ge=0.0, le=1.0)
    conflict_of_interest_declared: bool = False
    human_handoff_required: bool = True
    clinical_use_authorized: bool = False
    timestamp: str = Field(min_length=1, max_length=100)


class ReviewQueueItem(BaseModel):
    case_id: str = Field(min_length=1, max_length=200)
    model_id: str = Field(min_length=1, max_length=200)
    indication: str = Field(min_length=1, max_length=100)
    noul_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    choice_selected: str | None = Field(default=None, max_length=200)
    abstained: bool = False
    reason_for_review: str = Field(min_length=1, max_length=1000)
    priority: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    created_at: str = Field(min_length=1, max_length=100)


class SystemOneReviewerPanel:
    """Clinical safety reviewer panel for adjudicating model outputs."""

    def __init__(self, panel_id: str = "wysh.system-one.reviewer-panel.v1"):
        self._panel_id = panel_id
        self._reviewers: dict[str, ReviewerIdentity] = {}
        self._queue: dict[str, ReviewQueueItem] = {}
        self._reviews: dict[str, ReviewRecord] = {}
        self._review_ids: set[str] = set()

    def register_reviewer(self, reviewer: ReviewerIdentity) -> None:
        if reviewer.reviewer_id in self._reviewers:
            raise ReviewerError(f"reviewer {reviewer.reviewer_id} already registered")
        self._reviewers[reviewer.reviewer_id] = reviewer

    def add_to_queue(self, item: ReviewQueueItem) -> None:
        if item.case_id in self._queue:
            raise ReviewerError(f"case {item.case_id} already in review queue")
        self._queue[item.case_id] = item

    def get_queue(self, reviewer_role: ReviewerRole | None = None) -> list[ReviewQueueItem]:
        items = list(self._queue.values())
        if reviewer_role is not None:
            # In a real system, roles would filter visibility; here all reviewers see all
            pass
        return sorted(items, key=lambda item: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(item.priority, 99))

    def submit_review(
        self,
        record_id: str,
        case_id: str,
        model_id: str,
        reviewer_id: str,
        decision: ReviewDecision,
        rationale: str,
        confidence_in_decision: float,
        conflict_of_interest_declared: bool = False,
    ) -> ReviewRecord:
        if record_id in self._review_ids:
            raise ReviewerError(f"review {record_id} already exists")
        if reviewer_id not in self._reviewers:
            raise ReviewerError(f"reviewer {reviewer_id} is not registered")
        if case_id not in self._queue:
            raise ReviewerError(f"case {case_id} is not in the review queue")
        if not 0.0 <= confidence_in_decision <= 1.0:
            raise ReviewerError("confidence_in_decision must be in [0, 1]")
        if not rationale or len(rationale) > 2000:
            raise ReviewerError("rationale must be 1-2000 characters")

        reviewer = self._reviewers[reviewer_id]
        if reviewer.conflict_of_interest and not conflict_of_interest_declared:
            raise ReviewerError("reviewer has declared conflict of interest but did not acknowledge it")

        human_handoff_required = decision in {"ABSTAIN", "REQUEST_REVISION"}
        clinical_use_authorized = False  # Reviewer sign-off never auto-approves clinical use

        record = ReviewRecord(
            record_id=record_id,
            case_id=case_id,
            model_id=model_id,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer.role,
            decision=decision,
            rationale=rationale,
            confidence_in_decision=round(confidence_in_decision, 6),
            conflict_of_interest_declared=conflict_of_interest_declared,
            human_handoff_required=human_handoff_required,
            clinical_use_authorized=clinical_use_authorized,
            timestamp=self._utc_now(),
        )
        self._review_ids.add(record_id)
        self._reviews[record_id] = record
        # Remove from queue once reviewed
        self._queue.pop(case_id, None)
        return record

    def get_review(self, record_id: str) -> ReviewRecord | None:
        return self._reviews.get(record_id)

    def get_case_reviews(self, case_id: str) -> list[ReviewRecord]:
        return [r for r in self._reviews.values() if r.case_id == case_id]

    def pending_count(self) -> int:
        return len(self._queue)

    def completed_count(self) -> int:
        return len(self._reviews)

    def public_status(self) -> dict[str, object]:
        return {
            "panel_id": self._panel_id,
            "registered_reviewers": len(self._reviewers),
            "pending_reviews": self.pending_count(),
            "completed_reviews": self.completed_count(),
            "synthetic_only": True,
            "clinical_use_authorized": False,
            "deny_by_default": True,
            "reviewer_roles": sorted({r.role for r in self._reviewers.values()}),
        }

    def snapshot(self) -> list[dict[str, object]]:
        return [record.model_dump() for record in self._reviews.values()]

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
