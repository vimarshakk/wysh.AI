"""Tests for the System One feature extractor.

Deterministic feature extraction from typed clinical facts. Same input must
always produce the same feature vector; no free text or PHI is accepted.
"""

from __future__ import annotations

import pytest

from app.feature_extractor import (
    ClinicalFact,
    FeatureExtractorError,
    extract,
    required_metrics_for,
)


def _fact(source_id: str, source_type: str, metric: str | None = None, value: float | None = None, recorded_at: str = "2026-01-01T00:00:00Z", code: str | None = None) -> ClinicalFact:
    return ClinicalFact(source_id=source_id, source_type=source_type, metric=metric, value=value, recorded_at=recorded_at, code=code)


def test_deterministic_output() -> None:
    facts = [
        _fact("obs-1", "observation", "hba1c_percent", 7.2),
        _fact("obs-2", "observation", "mean_glucose_mg_dl", 154.0),
        _fact("cond-1", "condition", code="diabetes"),
    ]
    first = extract(facts)
    second = extract(facts)
    assert first.feature_names == second.feature_names
    assert first.values == second.values
    assert first.input_hash == second.input_hash


def test_feature_names_and_values_bounded() -> None:
    facts = [_fact("obs-1", "observation", "hba1c_percent", 7.2)]
    vector = extract(facts)
    assert len(vector.feature_names) == len(vector.values)
    assert all(isinstance(v, float) for v in vector.values)
    assert "hba1c_percent_count" in vector.feature_names
    assert "flag_diabetes" in vector.feature_names


def test_missing_metrics_flagged() -> None:
    facts = [_fact("obs-1", "observation", "hba1c_percent", 7.2)]
    vector = extract(facts)
    assert "mean_glucose_mg_dl" in vector.missing_flags
    assert "bp_systolic_mmhg" in vector.missing_flags


def test_invalid_value_raises() -> None:
    facts = [_fact("obs-1", "observation", "hba1c_percent", -1.0)]
    with pytest.raises(FeatureExtractorError):
        extract(facts)


def test_too_many_facts_raises() -> None:
    facts = [_fact(f"obs-{i}", "observation", "hba1c_percent", 7.0) for i in range(501)]
    with pytest.raises(FeatureExtractorError):
        extract(facts)


def test_binary_flags() -> None:
    facts = [_fact("cond-1", "condition", code="diabetes"), _fact("cond-2", "condition", code="hypertension")]
    vector = extract(facts)
    name_to_value = dict(zip(vector.feature_names, vector.values))
    assert name_to_value["flag_diabetes"] == 1.0
    assert name_to_value["flag_hypertension"] == 1.0
    assert name_to_value["flag_chronic_kidney_disease"] == 0.0


def test_required_metrics_for_indication() -> None:
    assert required_metrics_for("diabetes") == ("hba1c_percent", "mean_glucose_mg_dl", "age_years")
    assert required_metrics_for("hypertension") == ("bp_systolic_mmhg", "bp_diastolic_mmhg", "age_years")
    assert required_metrics_for("chronic_kidney_disease") == ("egfr_ml_min_1_73m2", "urine_acr_mg_g", "age_years")
    assert required_metrics_for("general") == ()
