"""Tests for the System One drift monitoring module.

PSI-based feature drift detection, calibration drift, and retraining triggers.
Synthetic-only.
"""

from __future__ import annotations

import pytest  # noqa

from app.system_one.drift_monitor import (
    DriftConfig,
    DriftResult,
    SystemOneDriftMonitor,
    default_drift_config,
)


def test_default_drift_config() -> None:
    config = DriftConfig()
    assert config.psi_threshold == 0.2
    assert config.calibration_threshold == 0.05
    assert config.min_reference_n == 30
    assert config.min_current_n == 30
    assert config.retraining_trigger_enabled is True
    assert config.synthetic_only is True
    assert config.clinical_use_authorized is False


def test_drift_monitor_public_status() -> None:
    monitor = SystemOneDriftMonitor()
    status = monitor.public_status()
    assert status["psi_threshold"] == 0.2
    assert status["calibration_threshold"] == 0.05
    assert status["evaluations_recorded"] == 0
    assert status["synthetic_only"] is True
    assert status["clinical_use_authorized"] is False


def test_psi_identical_distributions() -> None:
    monitor = SystemOneDriftMonitor()
    ref = [1.0, 2.0, 3.0, 4.0, 5.0] * 10
    cur = [1.0, 2.0, 3.0, 4.0, 5.0] * 10
    psi = monitor._psi(ref, cur)
    assert psi < 0.01  # Should be near zero for identical distributions


def test_psi_different_distributions() -> None:
    monitor = SystemOneDriftMonitor()
    ref = [1.0, 1.0, 1.0, 1.0, 1.0] * 10
    cur = [10.0, 10.0, 10.0, 10.0, 10.0] * 10
    psi = monitor._psi(ref, cur)
    assert psi > 0.1  # Should be high for very different distributions


def test_evaluate_feature_drift_stable() -> None:
    monitor = SystemOneDriftMonitor()
    ref = list(range(1, 101))
    cur = list(range(1, 101))
    result = monitor.evaluate_feature_drift("test_feature", ref, cur)
    assert result.drift_status == "STABLE"
    assert result.drift_detected is False


def test_evaluate_feature_drift_insufficient_sample() -> None:
    monitor = SystemOneDriftMonitor()
    ref = [1.0, 2.0, 3.0]
    cur = [1.0, 2.0, 3.0]
    result = monitor.evaluate_feature_drift("test_feature", ref, cur)
    assert result.drift_status == "INSUFFICIENT_SAMPLE"
    assert result.drift_detected is False


def test_evaluate_calibration_drift_stable() -> None:
    monitor = SystemOneDriftMonitor()
    ref_probs = [0.1, 0.2, 0.8, 0.9] * 10
    ref_labels = [0, 0, 1, 1] * 10
    cur_probs = [0.1, 0.2, 0.8, 0.9] * 10
    cur_labels = [0, 0, 1, 1] * 10
    result = monitor.evaluate_calibration_drift(
        "m1", "diabetes", ref_probs, ref_labels, cur_probs, cur_labels
    )
    assert result.drift_detected is False
    assert result.ece_delta < 0.01


def test_evaluate_calibration_drift_detected() -> None:
    monitor = SystemOneDriftMonitor()
    ref_probs = [0.1, 0.2, 0.8, 0.9] * 10
    ref_labels = [0, 0, 1, 1] * 10
    cur_probs = [0.9, 0.8, 0.2, 0.1] * 10
    cur_labels = [0, 0, 1, 1] * 10
    result = monitor.evaluate_calibration_drift(
        "m1", "diabetes", ref_probs, ref_labels, cur_probs, cur_labels
    )
    assert result.drift_detected is True
    assert result.drift_status == "DRIFT"


def test_evaluate_retraining_trigger() -> None:
    monitor = SystemOneDriftMonitor()
    feature_results = [
        DriftResult(
            feature_name="hba1c",
            reference_mean=6.0,
            reference_std=1.0,
            current_mean=7.5,
            current_std=1.2,
            psi=0.25,
            drift_status="DRIFT",
            drift_detected=True,
        )
    ]
    result = monitor.evaluate_retraining_trigger(
        "m1", "diabetes", feature_results, None
    )
    assert result.trigger_activated is True
    assert result.recommended_action == "RETRAINING_REVIEW_REQUIRED"
    assert len(result.reasons) == 1


def test_record_drift_evaluation() -> None:
    monitor = SystemOneDriftMonitor()
    feature_results = [
        DriftResult(
            feature_name="hba1c",
            reference_mean=6.0,
            reference_std=1.0,
            current_mean=7.5,
            current_std=1.2,
            psi=0.1,
            drift_status="STABLE",
            drift_detected=False,
        )
    ]
    record = monitor.record_drift_evaluation(
        "m1", "diabetes", feature_results, None,
        monitor.evaluate_retraining_trigger("m1", "diabetes", feature_results, None),
    )
    assert record["model_id"] == "m1"
    assert record["indication"] == "diabetes"
    assert record["record_sha256"] is not None
    assert len(record["record_sha256"]) == 64


def test_get_drift_history() -> None:
    monitor = SystemOneDriftMonitor()
    assert monitor.get_drift_history() == []
    feature_results = [
        DriftResult(
            feature_name="hba1c",
            reference_mean=6.0,
            reference_std=1.0,
            current_mean=7.5,
            current_std=1.2,
            psi=0.1,
            drift_status="STABLE",
            drift_detected=False,
        )
    ]
    trigger = monitor.evaluate_retraining_trigger("m1", "diabetes", feature_results, None)
    monitor.record_drift_evaluation("m1", "diabetes", feature_results, None, trigger)
    assert len(monitor.get_drift_history()) == 1


def test_default_drift_config_function() -> None:
    config = default_drift_config()
    assert config.psi_threshold == 0.2
    assert config.synthetic_only is True
