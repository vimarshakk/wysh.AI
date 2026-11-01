"""Tests for the System One routing engine.

Model selection by indication, bounded fallback chain, missing-metric
detection, and abstention when no model can produce a decision.
"""

from __future__ import annotations

import pytest

from app.decision_model import SystemOneDecisionModel
from app.feature_extractor import ClinicalFact, extract
from app.routing_engine import RoutingEngine


def _diabetes_facts() -> list[ClinicalFact]:
    return [
        ClinicalFact(source_id="obs-1", source_type="observation", metric="hba1c_percent", value=7.2, recorded_at="2026-01-01T00:00:00Z"),
        ClinicalFact(source_id="obs-2", source_type="observation", metric="mean_glucose_mg_dl", value=154.0, recorded_at="2026-01-01T00:00:00Z"),
        ClinicalFact(source_id="obs-3", source_type="observation", metric="age_years", value=55.0, recorded_at="2026-01-01T00:00:00Z"),
    ]


def test_model_selection_by_indication() -> None:
    engine = RoutingEngine(SystemOneDecisionModel())
    vector = extract(_diabetes_facts())
    result = engine.route("diabetes", vector)
    assert result.indication == "diabetes"
    assert result.selected_model == "wysh.synthetic.diabetes.review.v1"
    assert result.model_path in {"logistic_regression", "threshold_rules"}


def test_unknown_indication_abstains() -> None:
    engine = RoutingEngine(SystemOneDecisionModel())
    vector = extract(_diabetes_facts())
    result = engine.route("general", vector)
    assert result.abstained is True
    assert result.selected_model is None
    assert "no decision model registered" in (result.abstention_reason or "")


def test_missing_required_metrics_detected() -> None:
    engine = RoutingEngine(SystemOneDecisionModel())
    vector = extract([ClinicalFact(source_id="obs-1", source_type="observation", metric="hba1c_percent", value=5.0, recorded_at="2026-01-01T00:00:00Z")])
    result = engine.route("diabetes", vector)
    assert "mean_glucose_mg_dl" in result.missing_required_metrics
    assert "age_years" in result.missing_required_metrics


def test_route_attempts_recorded() -> None:
    engine = RoutingEngine(SystemOneDecisionModel())
    vector = extract(_diabetes_facts())
    result = engine.route("diabetes", vector)
    assert len(result.route_attempts) >= 1
    assert all(attempt.status == "success" for attempt in result.route_attempts)


def test_fallback_chain_bounded() -> None:
    engine = RoutingEngine(SystemOneDecisionModel())
    vector = extract(_diabetes_facts())
    result = engine.route("diabetes", vector)
    attempt_ids = [attempt.model_id for attempt in result.route_attempts]
    assert len(attempt_ids) <= 3
