"""Tests for the System One training pipeline.

Pipeline status, manifest structure, synthetic-only enforcement, and
CLINICALLY_APPROVED gate.
"""

from __future__ import annotations

import pytest

from app.system_one.training_pipeline import (
    SystemOneTrainingPipeline,
    TrainingManifest,
)


def test_training_manifest_structure() -> None:
    manifest = TrainingManifest(
        experiment_id="test-exp-1",
        model_id="wysh.system-one.diabetes.v1",
        indication="diabetes",
    )
    assert manifest.experiment_id == "test-exp-1"
    assert manifest.model_id == "wysh.system-one.diabetes.v1"
    assert manifest.indication == "diabetes"
    assert manifest.clinical_use_authorized is False
    assert manifest.synthetic_only is True
    assert manifest.schema_version == "system-one-training-v1"


def test_pipeline_public_status() -> None:
    pipeline = SystemOneTrainingPipeline()
    status = pipeline.public_status()
    assert status["pipeline"] == "system_one_training_v1"
    assert status["synthetic_only"] is True
    assert status["clinical_use_authorized"] is False
    assert status["deny_by_default"] is True
    assert "load_governed_dataset" in status["stages"]
    assert "rlcd_calibrate" in status["stages"]
    assert "register_lifecycle" in status["stages"]


def test_pipeline_run_unknown_dataset_raises() -> None:
    pipeline = SystemOneTrainingPipeline()
    with pytest.raises(Exception):
        pipeline.run(
            model_id="wysh.system-one.test.v1",
            indication="diabetes",
            dataset_id="wysh.synthetic.nonexistent.v1",
            dataset_version="1.0.0",
        )
