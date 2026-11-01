"""Tests for the System One retraining trigger pipeline.

Retraining trigger evaluation, trigger management, trigger summary.
Synthetic-only.
"""

from __future__ import annotations

import pytest

from app.system_one.retraining_pipeline import (
    RetrainingPipeline,
    RetrainingTriggerConfig,
    RetrainingTriggerEvent,
    RetrainingTriggerError,
    default_retraining_config,
)


def test_default_retraining_config() -> None:
    config = RetrainingTriggerConfig()
    assert config.drift_psi_threshold == 0.2
    assert config.calibration_ece_delta_threshold == 0.05
    assert config.adverse_event_rate_threshold == 0.05
    assert config.min_inferences_for_trigger == 100
    assert config.auto_trigger_retraining is False
    assert config.synthetic_only is True
    assert config.clinical_use_authorized is False


def test_retraining_pipeline_public_status() -> None:
    pipeline = RetrainingPipeline()
    status = pipeline.public_status()
    assert status["total_triggers"] == 0
    assert status["open_triggers"] == 0
    assert status["pending_retraining"] == 0
    assert status["synthetic_only"] is True
    assert status["clinical_use_authorized"] is False


def test_create_trigger() -> None:
    pipeline = RetrainingPipeline()
    event = pipeline.create_trigger(
        trigger_id="tr-1",
        model_id="m1",
        indication="diabetes",
        trigger_type="DRIFT",
        severity="HIGH",
        description="Feature drift detected",
        retraining_recommended=True,
    )
    assert event.trigger_id == "tr-1"
    assert event.model_id == "m1"
    assert event.indication == "diabetes"
    assert event.trigger_type == "DRIFT"
    assert event.severity == "HIGH"
    assert event.retraining_recommended is True
    assert event.status == "OPEN"
    assert pipeline.public_status()["total_triggers"] == 1


def test_create_duplicate_trigger_raises() -> None:
    pipeline = RetrainingPipeline()
    pipeline.create_trigger(
        trigger_id="tr-1",
        model_id="m1",
        indication="diabetes",
        trigger_type="DRIFT",
        severity="HIGH",
        description="Test",
        retraining_recommended=True,
    )
    with pytest.raises(RetrainingTriggerError):
        pipeline.create_trigger(
            trigger_id="tr-1",
            model_id="m1",
            indication="diabetes",
            trigger_type="DRIFT",
            severity="HIGH",
            description="Test",
            retraining_recommended=True,
        )


def test_create_trigger_invalid_severity() -> None:
    pipeline = RetrainingPipeline()
    with pytest.raises(RetrainingTriggerError):
        pipeline.create_trigger(
            trigger_id="tr-1",
            model_id="m1",
            indication="diabetes",
            trigger_type="DRIFT",
            severity="INVALID",
            description="Test",
            retraining_recommended=True,
        )


def test_evaluate_drift_trigger_no_drift() -> None:
    pipeline = RetrainingPipeline()
    event = pipeline.evaluate_drift_trigger(
        trigger_id="tr-1",
        model_id="m1",
        indication="diabetes",
        psi=0.1,
        ece_delta=0.02,
    )
    assert event.retraining_recommended is False
    assert event.severity == "LOW"
    assert "No significant drift" in event.description


def test_evaluate_drift_trigger_with_drift() -> None:
    pipeline = RetrainingPipeline()
    event = pipeline.evaluate_drift_trigger(
        trigger_id="tr-1",
        model_id="m1",
        indication="diabetes",
        psi=0.25,
        ece_delta=0.03,
    )
    assert event.retraining_recommended is True
    assert event.severity == "MEDIUM"
    assert "PSI=0.25" in event.description


def test_evaluate_adverse_event_trigger_low_rate() -> None:
    pipeline = RetrainingPipeline()
    event = pipeline.evaluate_adverse_event_trigger(
        trigger_id="tr-1",
        model_id="m1",
        indication="diabetes",
        total_inferences=1000,
        adverse_event_count=3,
    )
    assert event.retraining_recommended is False
    assert event.severity == "LOW"


def test_evaluate_adverse_event_trigger_high_rate() -> None:
    pipeline = RetrainingPipeline()
    event = pipeline.evaluate_adverse_event_trigger(
        trigger_id="tr-1",
        model_id="m1",
        indication="diabetes",
        total_inferences=1000,
        adverse_event_count=150,
    )
    assert event.retraining_recommended is True
    assert event.severity == "CRITICAL"
    assert "0.06" in event.description or "0.0" in event.description


def test_get_trigger() -> None:
    pipeline = RetrainingPipeline()
    pipeline.create_trigger(
        trigger_id="tr-1",
        model_id="m1",
        indication="diabetes",
        trigger_type="DRIFT",
        severity="HIGH",
        description="Test",
        retraining_recommended=True,
    )
    event = pipeline.get_trigger("tr-1")
    assert event is not None
    assert event.trigger_id == "tr-1"
    assert pipeline.get_trigger("tr-999") is None


def test_update_trigger_status() -> None:
    pipeline = RetrainingPipeline()
    pipeline.create_trigger(
        trigger_id="tr-1",
        model_id="m1",
        indication="diabetes",
        trigger_type="DRIFT",
        severity="HIGH",
        description="Test",
        retraining_recommended=True,
    )
    updated = pipeline.update_trigger_status(
        trigger_id="tr-1",
        status="APPROVED",
        retraining_completed=True,
        completion_date="2026-01-01T00:00:00Z",
    )
    assert updated.status == "APPROVED"
    assert updated.retraining_completed is True
    assert updated.completion_date == "2026-01-01T00:00:00Z"


def test_update_trigger_invalid_status() -> None:
    pipeline = RetrainingPipeline()
    pipeline.create_trigger(
        trigger_id="tr-1",
        model_id="m1",
        indication="diabetes",
        trigger_type="DRIFT",
        severity="HIGH",
        description="Test",
        retraining_recommended=True,
    )
    with pytest.raises(RetrainingTriggerError):
        pipeline.update_trigger_status(
            trigger_id="tr-1",
            status="INVALID",
        )


def test_get_open_triggers() -> None:
    pipeline = RetrainingPipeline()
    pipeline.create_trigger(
        trigger_id="tr-1",
        model_id="m1",
        indication="diabetes",
        trigger_type="DRIFT",
        severity="HIGH",
        description="Open",
        retraining_recommended=True,
    )
    pipeline.create_trigger(
        trigger_id="tr-2",
        model_id="m1",
        indication="hypertension",
        trigger_type="ADVERSE_EVENT",
        severity="LOW",
        description="Closed",
        retraining_recommended=True,
    )
    pipeline.update_trigger_status("tr-2", "COMPLETED")
    open_triggers = pipeline.get_open_triggers()
    assert len(open_triggers) == 1
    assert open_triggers[0].trigger_id == "tr-1"


def test_get_pending_retraining() -> None:
    pipeline = RetrainingPipeline()
    pipeline.create_trigger(
        trigger_id="tr-1",
        model_id="m1",
        indication="diabetes",
        trigger_type="DRIFT",
        severity="HIGH",
        description="Pending",
        retraining_recommended=True,
    )
    pipeline.create_trigger(
        trigger_id="tr-2",
        model_id="m1",
        indication="hypertension",
        trigger_type="ADVERSE_EVENT",
        severity="LOW",
        description="Not recommended",
        retraining_recommended=False,
    )
    pending = pipeline.get_pending_retraining()
    assert len(pending) == 1
    assert pending[0].trigger_id == "tr-1"


def test_get_trigger_summary() -> None:
    pipeline = RetrainingPipeline()
    pipeline.create_trigger(
        trigger_id="tr-1",
        model_id="m1",
        indication="diabetes",
        trigger_type="DRIFT",
        severity="CRITICAL",
        description="Test",
        retraining_recommended=True,
    )
    summary = pipeline.get_trigger_summary()
    assert summary["total_triggers"] == 1
    assert summary["open_triggers"] == 1
    assert summary["pending_retraining"] == 1
    assert summary["severity_distribution"]["CRITICAL"] == 1
    assert summary["type_distribution"]["DRIFT"] == 1
    assert summary["synthetic_only"] is True
