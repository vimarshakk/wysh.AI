"""Tests for the System One clinical safety reviewer panel.

Reviewer registration, queue management, review submission, audit records.
Synthetic-only.
"""

from __future__ import annotations

import pytest

from app.system_one.reviewer_panel import (
    ReviewDecision,
    ReviewerIdentity,
    ReviewerRole,
    ReviewQueueItem,
    SystemOneReviewerPanel,
)


def test_register_reviewer() -> None:
    panel = SystemOneReviewerPanel()
    reviewer = ReviewerIdentity(
        reviewer_id="rev-1",
        name="Dr. Safety Reviewer",
        role='clinician-safety',
        qualifications="MD, Board Certified",
        conflict_of_interest="",
    )
    panel.register_reviewer(reviewer)
    status = panel.public_status()
    assert status["registered_reviewers"] == 1


def test_register_duplicate_reviewer_raises() -> None:
    panel = SystemOneReviewerPanel()
    reviewer = ReviewerIdentity(
        reviewer_id="rev-1", name="Dr. X", role='clinician-safety',
        qualifications="MD",
    )
    panel.register_reviewer(reviewer)
    with pytest.raises(Exception):
        panel.register_reviewer(reviewer)


def test_add_to_queue_and_get_queue() -> None:
    panel = SystemOneReviewerPanel()
    item = ReviewQueueItem(
        case_id="case-1",
        model_id="m1",
        indication="diabetes",
        noul_probability=0.6,
        choice_selected="review_required",
        abstained=False,
        reason_for_review="low confidence",
        priority="HIGH",
        created_at="2026-01-01T00:00:00Z",
    )
    panel.add_to_queue(item)
    queue = panel.get_queue()
    assert len(queue) == 1
    assert queue[0].case_id == "case-1"
    assert panel.pending_count() == 1


def test_submit_review() -> None:
    panel = SystemOneReviewerPanel()
    reviewer = ReviewerIdentity(
        reviewer_id="rev-1", name="Dr. Safety", role='clinician-safety',
        qualifications="MD",
    )
    panel.register_reviewer(reviewer)
    item = ReviewQueueItem(
        case_id="case-1", model_id="m1", indication="diabetes",
        noul_probability=0.6, choice_selected="review_required",
        abstained=False, reason_for_review="review needed", priority="MEDIUM",
        created_at="2026-01-01T00:00:00Z",
    )
    panel.add_to_queue(item)
    record = panel.submit_review(
        record_id="rev-rec-1",
        case_id="case-1",
        model_id="m1",
        reviewer_id="rev-1",
        decision='APPROVE',
        rationale="Model output is clinically reasonable.",
        confidence_in_decision=0.9,
    )
    assert record.record_id == "rev-rec-1"
    assert record.decision == 'APPROVE'
    assert record.clinical_use_authorized is False
    assert record.human_handoff_required is False
    assert panel.pending_count() == 0
    assert panel.completed_count() == 1


def test_submit_review_duplicate_raises() -> None:
    panel = SystemOneReviewerPanel()
    reviewer = ReviewerIdentity(
        reviewer_id="rev-1", name="Dr. Safety", role='clinician-safety',
        qualifications="MD",
    )
    panel.register_reviewer(reviewer)
    item = ReviewQueueItem(
        case_id="case-1", model_id="m1", indication="diabetes",
        noul_probability=0.6, choice_selected="review_required",
        abstained=False, reason_for_review="review needed", priority="MEDIUM",
        created_at="2026-01-01T00:00:00Z",
    )
    panel.add_to_queue(item)
    panel.submit_review(
        record_id="rev-rec-1", case_id="case-1", model_id="m1",
        reviewer_id="rev-1", decision='APPROVE',
        rationale="ok", confidence_in_decision=0.9,
    )
    with pytest.raises(Exception):
        panel.submit_review(
            record_id="rev-rec-1", case_id="case-1", model_id="m1",
            reviewer_id="rev-1", decision='REJECT',
            rationale="no", confidence_in_decision=0.9,
        )


def test_submit_review_unknown_reviewer_raises() -> None:
    panel = SystemOneReviewerPanel()
    item = ReviewQueueItem(
        case_id="case-1", model_id="m1", indication="diabetes",
        noul_probability=0.6, choice_selected="review_required",
        abstained=False, reason_for_review="review needed", priority="MEDIUM",
        created_at="2026-01-01T00:00:00Z",
    )
    panel.add_to_queue(item)
    with pytest.raises(Exception):
        panel.submit_review(
            record_id="rev-rec-1", case_id="case-1", model_id="m1",
            reviewer_id="unknown-rev", decision='APPROVE',
            rationale="ok", confidence_in_decision=0.9,
        )


def test_abstain_triggers_human_handoff() -> None:
    panel = SystemOneReviewerPanel()
    reviewer = ReviewerIdentity(
        reviewer_id="rev-1", name="Dr. Safety", role='clinician-safety',
        qualifications="MD",
    )
    panel.register_reviewer(reviewer)
    item = ReviewQueueItem(
        case_id="case-1", model_id="m1", indication="diabetes",
        noul_probability=0.5, choice_selected=None,
        abstained=True, reason_for_review="abstained", priority="HIGH",
        created_at="2026-01-01T00:00:00Z",
    )
    panel.add_to_queue(item)
    record = panel.submit_review(
        record_id="rev-rec-1", case_id="case-1", model_id="m1",
        reviewer_id="rev-1", decision='ABSTAIN',
        rationale="Model abstained; human review required.",
        confidence_in_decision=0.95,
    )
    assert record.human_handoff_required is True


def test_reviewer_roles() -> None:
    panel = SystemOneReviewerPanel()
    roles = ['clinician-safety', 'clinical-lead',
             'regulatory', 'ethics']
    for i, role in enumerate(roles):
        reviewer = ReviewerIdentity(
            reviewer_id=f"rev-{i}", name=f"Dr. {i}", role=role,
            qualifications="MD",
        )
        panel.register_reviewer(reviewer)
    status = panel.public_status()
    assert len(status["reviewer_roles"]) == 4
