"""Tests for the System One validation harness.

End-to-end validation pipeline: encoder -> heads -> RLCD -> validation engine.
Synthetic-only, deny-by-default.
"""

from __future__ import annotations

import pytest

from app.system_one.validation_harness import (
    SystemOneValidationHarness,
    ValidationHarnessError,
    ValidationHarnessResult,
)


def test_harness_public_status() -> None:
    harness = SystemOneValidationHarness()
    status = harness.public_status()
    assert status["harness"] == "system_one_validation_v1"
    assert status["synthetic_only"] is True
    assert status["clinical_use_authorized"] is False
    assert status["deny_by_default"] is True
    assert "load_governed_dataset" in status["stages"]
    assert "generate_report" in status["stages"]


def test_harness_unknown_dataset_raises() -> None:
    harness = SystemOneValidationHarness()
    with pytest.raises(ValidationHarnessError):
        harness.run(
            model_id="wysh.synthetic.diabetes.review.v1",
            indication="diabetes",
            dataset_id="wysh.synthetic.nonexistent.v1",
            dataset_version="1.0.0",
        )


def test_harness_result_structure() -> None:
    harness = SystemOneValidationHarness()
    result = harness.run(
        model_id="wysh.synthetic.diabetes.review.v1",
        indication="diabetes",
        dataset_id="wysh.synthetic.diabetes.review.v1",
        dataset_version="1.0.0",
    )
    assert isinstance(result, ValidationHarnessResult)
    assert result.model_id == "wysh.synthetic.diabetes.review.v1"
    assert result.indication == "diabetes"
    assert result.dataset_id == "wysh.synthetic.diabetes.review.v1"
    assert result.clinical_use_authorized is False
    assert result.synthetic_only is True
    assert result.report_id.startswith("validation-")
    assert result.provenance_hash is not None
    assert len(result.provenance_hash) == 64
    assert isinstance(result.subgroup_slices, list)
    assert result.n_cases >= 0
    assert result.n_abstained >= 0
    assert result.n_human_handoff >= 0
    assert 0.0 <= result.abstention_rate <= 1.0
    assert 0.0 <= result.human_handoff_rate <= 1.0
