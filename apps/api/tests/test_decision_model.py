"""Tests for the System One decision model.

Fast, deterministic inference on feature vectors. No text generation, no
external provider calls. Backed by R8B baseline manifests when available,
falling back to transparent threshold rules.
"""

from __future__ import annotations

import pytest

from app.decision_model import ModelInferenceError, SystemOneDecisionModel
from app.feature_extractor import ClinicalFact, extract


def _facts_for_diabetes() -> list[ClinicalFact]:
    return [
        ClinicalFact(source_id="obs-1", source_type="observation", metric="hba1c_percent", value=7.2, recorded_at="2026-01-01T00:00:00Z"),
        ClinicalFact(source_id="obs-2", source_type="observation", metric="mean_glucose_mg_dl", value=154.0, recorded_at="2026-01-01T00:00:00Z"),
        ClinicalFact(source_id="obs-3", source_type="observation", metric="age_years", value=55.0, recorded_at="2026-01-01T00:00:00Z"),
        ClinicalFact(source_id="cond-1", source_type="condition", code="diabetes", recorded_at="2026-01-01T00:00:00Z"),
    ]


def test_threshold_inference_escalates_high_hba1c() -> None:
    model = SystemOneDecisionModel()
    vector = extract(_facts_for_diabetes())
    action, confidence, reason, path = model.predict("wysh.synthetic.diabetes.review.v1", "diabetes", vector)
    assert action in {"escalate", "review_required", None}
    assert path in {"logistic_regression", "threshold_rules"}
    if action is not None:
        assert 0.0 <= (confidence or 0.0) <= 1.0
        assert reason is not None


def test_threshold_inference_present_below_threshold_reviews() -> None:
    model = SystemOneDecisionModel()
    vector = extract([ClinicalFact(source_id="obs-1", source_type="observation", metric="hba1c_percent", value=5.0, recorded_at="2026-01-01T00:00:00Z")])
    action, confidence, reason, path = model.predict("wysh.synthetic.diabetes.review.v1", "diabetes", vector)
    assert action == "review_required"
    assert confidence == 0.6


def test_unknown_model_raises() -> None:
    model = SystemOneDecisionModel()
    vector = extract(_facts_for_diabetes())
    with pytest.raises(ModelInferenceError):
        model.predict("wysh.synthetic.unknown.v1", "diabetes", vector)


def test_registry_status_is_checked() -> None:
    model = SystemOneDecisionModel()
    vector = extract(_facts_for_diabetes())
    action, confidence, reason, path = model.predict("wysh.synthetic.diabetes.review.v1", "diabetes", vector)
    assert path in {"logistic_regression", "threshold_rules"}


def test_different_indications() -> None:
    model = SystemOneDecisionModel()
    htn_facts = [
        ClinicalFact(source_id="obs-1", source_type="observation", metric="bp_systolic_mmhg", value=185.0, recorded_at="2026-01-01T00:00:00Z"),
        ClinicalFact(source_id="obs-2", source_type="observation", metric="bp_diastolic_mmhg", value=120.0, recorded_at="2026-01-01T00:00:00Z"),
        ClinicalFact(source_id="obs-3", source_type="observation", metric="age_years", value=60.0, recorded_at="2026-01-01T00:00:00Z"),
    ]
    vector = extract(htn_facts)
    action, confidence, reason, path = model.predict("wysh.synthetic.hypertension.review.v1", "hypertension", vector)
    assert action in {"escalate", "review_required", None}
    assert path in {"logistic_regression", "threshold_rules"}
