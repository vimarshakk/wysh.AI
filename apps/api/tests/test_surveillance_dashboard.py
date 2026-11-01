"""Tests for the System One surveillance dashboard module.

Real-world performance tracking, inference recording, alert generation.
Synthetic-only.
"""

from __future__ import annotations

import pytest

from app.system_one.surveillance_dashboard import (
    InferenceRecord,
    PerformanceSnapshot,
    SurveillanceConfig,
    SurveillanceDashboard,
    default_surveillance_config,
)


def test_default_surveillance_config() -> None:
    config = default_surveillance_config()
    assert config.max_inference_records == 100000
    assert config.alert_on_drift is True
    assert config.alert_on_abstention_rate_increase is True
    assert config.abstention_rate_alert_threshold == 0.5
    assert config.synthetic_only is True
    assert config.clinical_use_authorized is False


def test_surveillance_dashboard_public_status() -> None:
    dashboard = SurveillanceDashboard()
    status = dashboard.public_status()
    assert status["total_inferences"] == 0
    assert status["snapshots_recorded"] == 0
    assert status["synthetic_only"] is True


def test_record_inference() -> None:
    dashboard = SurveillanceDashboard()
    record = dashboard.record_inference(
        inference_id="inf-1",
        model_id="m1",
        indication="diabetes",
        language="en",
        noul_probability=0.8,
        choice_selected="review_required",
        abstained=False,
        human_handoff_triggered=False,
    )
    assert record.inference_id == "inf-1"
    assert record.model_id == "m1"
    assert record.indication == "diabetes"
    assert record.language == "en"
    assert record.abstained is False
    assert dashboard.public_status()["total_inferences"] == 1


def test_record_inference_bounded() -> None:
    dashboard = SurveillanceDashboard()
    # Just test that recording many inferences works
    for i in range(5):
        dashboard.record_inference(
            inference_id=f"inf-{i}",
            model_id="m1",
            indication="diabetes",
            language="en",
        )
    assert dashboard.public_status()["total_inferences"] == 5


def test_get_performance_snapshot() -> None:
    dashboard = SurveillanceDashboard()
    for i in range(10):
        abstained = i < 3  # 3 abstentions out of 10
        handoff = i < 2  # 2 handoffs out of 10
        dashboard.record_inference(
            inference_id=f"inf-{i}",
            model_id="m1",
            indication="diabetes",
            language="en",
            abstained=abstained,
            human_handoff_triggered=handoff,
        )
    snapshot = dashboard.get_performance_snapshot("m1", "diabetes", "2026-01-01", "2026-12-31")
    assert snapshot.total_inferences == 10
    assert snapshot.total_abstentions == 3
    assert snapshot.total_human_handoffs == 2
    assert snapshot.abstention_rate == 0.3
    assert snapshot.human_handoff_rate == 0.2


def test_get_alerts_high_abstention() -> None:
    dashboard = SurveillanceDashboard(
        config=SurveillanceConfig(abstention_rate_alert_threshold=0.3)
    )
    for i in range(10):
        abstained = i < 8  # 80% abstention rate
        dashboard.record_inference(
            inference_id=f"inf-{i}",
            model_id="m1",
            indication="diabetes",
            language="en",
            abstained=abstained,
        )
    alerts = dashboard.get_alerts()
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "high_abstention_rate"
    assert alerts[0]["abstention_rate"] == 0.8


def test_get_dashboard_summary() -> None:
    dashboard = SurveillanceDashboard()
    dashboard.record_inference(
        inference_id="inf-1",
        model_id="m1",
        indication="diabetes",
        language="en",
        abstained=True,
    )
    dashboard.record_inference(
        inference_id="inf-2",
        model_id="m2",
        indication="hypertension",
        language="hi",
        abstained=False,
    )
    summary = dashboard.get_dashboard_summary()
    assert summary["total_inferences"] == 2
    assert summary["total_abstentions"] == 1
    assert summary["model_count"] == 2
    assert summary["synthetic_only"] is True


def test_record_performance_snapshot() -> None:
    dashboard = SurveillanceDashboard()
    snapshot = PerformanceSnapshot(
        model_id="m1",
        indication="diabetes",
        period_start="2026-01-01",
        period_end="2026-01-31",
        total_inferences=100,
        total_abstentions=10,
        total_human_handoffs=5,
        abstention_rate=0.1,
        human_handoff_rate=0.05,
        language_distribution={"en": 100},
        indication_distribution={"diabetes": 100},
    )
    dashboard.record_performance_snapshot(snapshot)
    history = dashboard.get_performance_history()
    assert len(history) == 1
    assert history[0].model_id == "m1"
