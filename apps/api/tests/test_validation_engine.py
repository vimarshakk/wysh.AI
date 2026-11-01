"""Tests for the System One validation engine.

External validation, metrics (AUROC, AUPRC, Brier, ECE), subgroup analysis.
Synthetic-only.
"""

from __future__ import annotations

import pytest

from app.system_one.validation_engine import (
    SubgroupSlice,
    SystemOneValidationEngine,
    ValidationCase,
    ValidationReport,
)


def test_validation_case_creation() -> None:
    case = ValidationCase(
        case_id="case-1",
        indication="diabetes",
        language="en",
        age_band="55-64",
        sex="M",
        comorbidity_count=2,
        noul_probability=0.8,
        noul_confidence=0.9,
        noul_abstained=False,
        choice_selected="review_required",
        choice_confidence=0.85,
        choice_abstained=False,
        actual_outcome=1,
        choice_correct=True,
    )
    assert case.case_id == "case-1"
    assert case.indication == "diabetes"
    assert case.actual_outcome == 1


def test_engine_add_case() -> None:
    engine = SystemOneValidationEngine(model_id="m1", indication="diabetes")
    case = ValidationCase(
        case_id="c1", indication="diabetes", language="en", age_band="55-64",
        sex="M", comorbidity_count=1, noul_probability=0.7, noul_confidence=0.8,
        noul_abstained=False, choice_selected="review_required",
        choice_confidence=0.8, choice_abstained=False, actual_outcome=1,
        choice_correct=True,
    )
    engine.add_case(case)
    status = engine.public_status()
    assert status["n_cases"] == 1
    assert status["model_id"] == "m1"
    assert status["indication"] == "diabetes"


def test_engine_wrong_indication_raises() -> None:
    engine = SystemOneValidationEngine(model_id="m1", indication="diabetes")
    case = ValidationCase(
        case_id="c1", indication="hypertension", language="en", age_band="55-64",
        sex="M", comorbidity_count=1, noul_probability=0.7, noul_confidence=0.8,
        noul_abstained=False, choice_selected="review_required",
        choice_confidence=0.8, choice_abstained=False, actual_outcome=1,
        choice_correct=True,
    )
    with pytest.raises(Exception):
        engine.add_case(case)


def test_auroc_perfect() -> None:
    engine = SystemOneValidationEngine(model_id="m1", indication="diabetes")
    probs = [0.9, 0.8, 0.7, 0.6, 0.1, 0.2, 0.3, 0.4]
    labels = [1, 1, 1, 1, 0, 0, 0, 0]
    auroc = engine._auroc(probs, labels)
    assert auroc == 1.0


def test_auroc_random() -> None:
    engine = SystemOneValidationEngine(model_id="m1", indication="diabetes")
    probs = [0.5, 0.5, 0.5, 0.5]
    labels = [1, 1, 0, 0]
    auroc = engine._auroc(probs, labels)
    assert auroc is not None
    assert 0.0 <= auroc <= 1.0


def test_auroc_single_class_returns_none() -> None:
    engine = SystemOneValidationEngine(model_id="m1", indication="diabetes")
    auroc = engine._auroc([0.5, 0.6], [1, 1])
    assert auroc is None


def test_brier_score() -> None:
    engine = SystemOneValidationEngine(model_id="m1", indication="diabetes")
    probs = [0.0, 1.0, 0.5, 0.5]
    labels = [0, 1, 0, 1]
    brier = engine._brier_score(probs, labels)
    assert brier is not None
    assert 0.0 <= brier <= 1.0


def test_ece_perfect_calibration() -> None:
    engine = SystemOneValidationEngine(model_id="m1", indication="diabetes")
    probs = [0.05, 0.05, 0.95, 0.95]
    labels = [0, 0, 1, 1]
    ece = engine._ece(probs, labels)
    assert ece is not None
    assert ece < 0.1


def test_validation_report_synthetic_only() -> None:
    engine = SystemOneValidationEngine(model_id="m1", indication="diabetes")
    case = ValidationCase(
        case_id="c1", indication="diabetes", language="en", age_band="55-64",
        sex="M", comorbidity_count=1, noul_probability=0.8, noul_confidence=0.9,
        noul_abstained=False, choice_selected="review_required",
        choice_confidence=0.85, choice_abstained=False, actual_outcome=1,
        choice_correct=True,
    )
    engine.add_case(case)
    report = engine.generate_report(dataset_id="synthetic-test-v1")
    assert report.synthetic_only is True
    assert report.clinical_use_authorized is False
    assert report.model_id == "m1"
    assert report.indication == "diabetes"
    assert isinstance(report.subgroup_slices, list)


def test_subgroup_slice_structure() -> None:
    engine = SystemOneValidationEngine(model_id="m1", indication="diabetes")
    case = ValidationCase(
        case_id="c1", indication="diabetes", language="hi", age_band="55-64",
        sex="F", comorbidity_count=2, noul_probability=0.7, noul_confidence=0.85,
        noul_abstained=False, choice_selected="escalate",
        choice_confidence=0.9, choice_abstained=False, actual_outcome=1,
        choice_correct=True,
    )
    engine.add_case(case)
    report = engine.generate_report(dataset_id="synthetic-test-v1")
    languages = [s for s in report.subgroup_slices if s.dimension == "language"]
    assert len(languages) == 1
    assert languages[0].value == "hi"
    assert languages[0].n_cases == 1
