"""Tests for the System One adverse event reporting system.

Adverse event reporting, safety signals, regulatory reporting.
Synthetic-only.
"""

from __future__ import annotations

import pytest

from app.system_one.adverse_event_reporting import (  # noqa
    AdverseEventError,
    AdverseEventRecord,
    AdverseEventReportingSystem,
    SafetySignal,
    default_adverse_event_system,
)


def test_default_adverse_event_system() -> None:
    system = default_adverse_event_system()
    status = system.public_status()
    assert status["total_events"] == 0
    assert status["open_events"] == 0
    assert status["critical_events"] == 0
    assert status["open_signals"] == 0
    assert status["synthetic_only"] is True
    assert status["clinical_use_authorized"] is False


def test_report_adverse_event() -> None:
    system = AdverseEventReportingSystem()
    event = system.report_event(
        event_id="ev-1",
        model_id="m1",
        indication="diabetes",
        event_type="WRONG_ROUTING",
        severity="SERIOUS",
        description="Model gave wrong triage recommendation",
        reporter_id="rev-1",
        reporter_role="clinician-safety",
    )
    assert event.event_id == "ev-1"
    assert event.model_id == "m1"
    assert event.indication == "diabetes"
    assert event.event_type == "WRONG_ROUTING"
    assert event.severity == "SERIOUS"
    assert event.status == "OPEN"
    assert event.regulatory_reported is False
    assert system.public_status()["total_events"] == 1


def test_report_duplicate_event_raises() -> None:
    system = AdverseEventReportingSystem()
    system.report_event(
        event_id="ev-1",
        model_id="m1",
        indication="diabetes",
        event_type="WRONG_ROUTING",
        severity="MINOR",
        description="Test",
        reporter_id="rev-1",
        reporter_role="clinician-safety",
    )
    with pytest.raises(AdverseEventError):
        system.report_event(
            event_id="ev-1",
            model_id="m1",
            indication="diabetes",
            event_type="WRONG_ROUTING",
            severity="MINOR",
            description="Test",
            reporter_id="rev-1",
            reporter_role="clinician-safety",
        )


def test_update_event_status() -> None:
    system = AdverseEventReportingSystem()
    system.report_event(
        event_id="ev-1",
        model_id="m1",
        indication="diabetes",
        event_type="WRONG_ROUTING",
        severity="SERIOUS",
        description="Test",
        reporter_id="rev-1",
        reporter_role="clinician-safety",
    )
    updated = system.update_event_status(
        event_id="ev-1",
        status="RESOLVED",
        root_cause="Model drift",
        corrective_action="Retrain model",
    )
    assert updated.status == "RESOLVED"
    assert updated.root_cause == "Model drift"
    assert updated.corrective_action == "Retrain model"
    assert updated.resolution_date is not None


def test_get_open_events() -> None:
    system = AdverseEventReportingSystem()
    system.report_event(
        event_id="ev-1",
        model_id="m1",
        indication="diabetes",
        event_type="WRONG_ROUTING",
        severity="MINOR",
        description="Test 1",
        reporter_id="rev-1",
        reporter_role="clinician-safety",
    )
    system.report_event(
        event_id="ev-2",
        model_id="m1",
        indication="hypertension",
        event_type="SAFETY_SIGNAL",
        severity="CRITICAL",
        description="Test 2",
        reporter_id="rev-2",
        reporter_role="clinical-lead",
    )
    system.update_event_status("ev-1", "RESOLVED")
    open_events = system.get_open_events()
    assert len(open_events) == 1
    assert open_events[0].event_id == "ev-2"


def test_get_critical_events() -> None:
    system = AdverseEventReportingSystem()
    system.report_event(
        event_id="ev-1",
        model_id="m1",
        indication="diabetes",
        event_type="WRONG_ROUTING",
        severity="CRITICAL",
        description="Critical",
        reporter_id="rev-1",
        reporter_role="clinician-safety",
    )
    system.report_event(
        event_id="ev-2",
        model_id="m1",
        indication="hypertension",
        event_type="SAFETY_SIGNAL",
        severity="MINOR",
        description="Minor",
        reporter_id="rev-1",
        reporter_role="clinician-safety",
    )
    system.update_event_status("ev-1", "CLOSED")
    critical = system.get_critical_events()
    assert len(critical) == 0  # Only non-CLOSED critical events


def test_report_regulatory() -> None:
    system = AdverseEventReportingSystem()
    system.report_event(
        event_id="ev-1",
        model_id="m1",
        indication="diabetes",
        event_type="WRONG_ROUTING",
        severity="SERIOUS",
        description="Test",
        reporter_id="rev-1",
        reporter_role="clinician-safety",
    )
    updated = system.report_regulatory("ev-1")
    assert updated.regulatory_reported is True
    assert updated.regulatory_report_date is not None


def test_create_safety_signal() -> None:
    system = AdverseEventReportingSystem()
    signal = system.create_safety_signal(
        signal_id="sig-1",
        model_id="m1",
        indication="diabetes",
        signal_type="HIGH_ABSTENTION",
        description="High abstention rate observed",
        confidence_score=0.85,
        recommended_action="Review model calibration",
    )
    assert signal.signal_id == "sig-1"
    assert signal.signal_type == "HIGH_ABSTENTION"
    assert signal.confidence_score == 0.85
    assert signal.status == "OPEN"


def test_update_signal_status() -> None:
    system = AdverseEventReportingSystem()
    system.create_safety_signal(
        signal_id="sig-1",
        model_id="m1",
        indication="diabetes",
        signal_type="HIGH_ABSTENTION",
        description="Test",
        confidence_score=0.5,
        recommended_action="Review",
    )
    updated = system.update_signal_status("sig-1", "RESOLVED")
    assert updated.status == "RESOLVED"


def test_get_event_summary() -> None:
    system = AdverseEventReportingSystem()
    system.report_event(
        event_id="ev-1",
        model_id="m1",
        indication="diabetes",
        event_type="WRONG_ROUTING",
        severity="CRITICAL",
        description="Critical event",
        reporter_id="rev-1",
        reporter_role="clinician-safety",
    )
    system.report_event(
        event_id="ev-2",
        model_id="m1",
        indication="hypertension",
        event_type="SAFETY_SIGNAL",
        severity="MINOR",
        description="Minor event",
        reporter_id="rev-1",
        reporter_role="clinician-safety",
    )
    summary = system.get_event_summary()
    assert summary["total_events"] == 2
    assert summary["open_events"] == 2
    assert summary["critical_events"] == 1
    assert summary["synthetic_only"] is True
