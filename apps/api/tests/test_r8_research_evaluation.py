from __future__ import annotations

import pytest

from app.ml_governance import GovernanceError, load_governed_dataset
from app.model_lifecycle import ModelLifecycleStore
from app.research_evaluation import INSUFFICIENT_SAMPLE, auprc, auroc, brier_score, calibration, leakage_checks


def test_three_research_datasets_are_original_synthetic_and_contract_bound():
    for dataset_id in ("wysh.synthetic.diabetes.review.v1", "wysh.synthetic.hypertension.review.v1", "wysh.synthetic.ckd.review.v1"):
        dataset = load_governed_dataset(dataset_id)
        assert len(dataset.rows) == 20
        assert dataset.label_name.startswith("synthetic_") or dataset.label_name == "synthetic_review_required"


def test_small_cohort_fails_closed_for_performance_metrics():
    labels = [0, 1] * 10
    probabilities = [0.1, 0.9] * 10
    assert auroc(labels, probabilities).status == INSUFFICIENT_SAMPLE
    assert auprc(labels, probabilities).status == INSUFFICIENT_SAMPLE
    assert brier_score(labels, probabilities).status == INSUFFICIENT_SAMPLE
    assert calibration(labels, probabilities).status == INSUFFICIENT_SAMPLE


def test_leakage_checks_detect_future_feature_cutoff():
    rows = [{"patient_id": "synthetic-a", "observed_at": "2025-01-01", "feature_cutoff": "2025-01-02"}]
    assert leakage_checks(rows, ("value",))["temporal_feature_leakage"] == "FAIL"


def test_model_lifecycle_blocks_clinical_approval_and_requires_evidence():
    store = ModelLifecycleStore()
    model_id = "wysh.synthetic.diabetes.review.v1"
    with pytest.raises(GovernanceError):
        store.transition(model_id, "ENGINEERING_VERIFIED", actor="system:test", reason="missing evidence")
    model = store.transition(model_id, "ENGINEERING_VERIFIED", actor="system:test", reason="evidence", evidence={"reproducibility": "PASS", "leakage": "PASS", "dataset_governance": "PASS", "evaluation_report": "PRESENT"})
    assert model["status"] == "ENGINEERING_VERIFIED"
    with pytest.raises(GovernanceError):
        store.transition(model_id, "CLINICALLY_APPROVED", actor="system:test", reason="not allowed")


def test_model_lifecycle_requires_qualified_reviewer_for_review_pending():
    store = ModelLifecycleStore()
    model_id = "wysh.synthetic.hypertension.review.v1"
    store.transition(model_id, "ENGINEERING_VERIFIED", actor="system:test", reason="evidence", evidence={"reproducibility": "PASS", "leakage": "PASS", "dataset_governance": "PASS", "evaluation_report": "PRESENT"})
    with pytest.raises(GovernanceError):
        store.transition(model_id, "CLINICAL_REVIEW_PENDING", actor="system:test", reason="review")
    assert store.transition(model_id, "CLINICAL_REVIEW_PENDING", actor="qualified-reviewer:synthetic", reason="manual review requested")["status"] == "CLINICAL_REVIEW_PENDING"
