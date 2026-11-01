from __future__ import annotations

import hashlib
import json

import pytest

from app.imaging_research_execution import SyntheticPixelTask, execute_synthetic_pixel_task
from app.ml_governance import load_governed_dataset, train_baseline, train_interpretable_comparator
from app.research_evaluation import INSUFFICIENT_SAMPLE, calibration_parameters, classification_metrics


def test_three_disease_logistic_and_interpretable_comparator_are_reproducible():
    for dataset_id in ("wysh.synthetic.diabetes.review.v1", "wysh.synthetic.hypertension.review.v1", "wysh.synthetic.ckd.review.v1"):
        dataset = load_governed_dataset(dataset_id)
        logistic = train_baseline(dataset)
        comparator = train_interpretable_comparator(dataset)
        assert logistic["provenance_hash"] == train_baseline(dataset)["provenance_hash"]
        assert comparator["provenance_hash"] == train_interpretable_comparator(dataset)["provenance_hash"]
        assert logistic["clinical_use_authorized"] is False and comparator["clinical_use_authorized"] is False


def test_metric_pathological_inputs_are_explicitly_invalid_or_insufficient():
    assert classification_metrics([], []) ["status"] == "INVALID_DATA"
    assert classification_metrics([0] * 30, [0.1] * 30)["status"] == INSUFFICIENT_SAMPLE
    assert classification_metrics([0, 1] * 15, [0.5] * 30)["status"] == "VALID"
    assert classification_metrics([0, 1] * 15, [float("nan")] * 30)["status"] == "INVALID_DATA"
    assert calibration_parameters([0, 1] * 15, [0.2, 0.8] * 15)["status"] == INSUFFICIENT_SAMPLE


def test_native_imaging_task_is_non_diagnostic_and_hash_bound():
    pixels = [0, 10, 20, 30]
    digest = hashlib.sha256(json.dumps(pixels, separators=(",", ":")).encode()).hexdigest()
    task = SyntheticPixelTask(study_id="study-r13", patient_id="synthetic-r13", modality="DX", width=2, height=2, pixels=pixels, expected_sha256=digest)
    result = execute_synthetic_pixel_task(task)
    assert result["status"] == "RESEARCH_DESCRIPTIVE"
    assert result["diagnostic_interpretation"] is False
    bad = task.model_copy(update={"expected_sha256": "b" * 64})
    assert execute_synthetic_pixel_task(bad)["status"] == "ABSTAINED"


def test_native_imaging_task_rejects_dimension_mismatch():
    with pytest.raises(ValueError):
        SyntheticPixelTask(study_id="study-r13", patient_id="synthetic-r13", modality="DX", width=2, height=2, pixels=[1, 2, 3], expected_sha256="a" * 64)
