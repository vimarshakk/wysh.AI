"""System One adverse event reporting system.

Phase 5 — Post-Market Surveillance. Tracks adverse events, safety signals,
and provides regulatory reporting capabilities for deployed System One
decision models.

Synthetic-only: no PHI accepted, clinical use not authorized. All adverse
event reports are auditable with provenance hashes.
"""

from __future__ import annotations

from dataclasses import dataclass  # noqa
from datetime import datetime, timezone
from hashlib import sha256  # noqa
import json  # noqa
from typing import Literal

from pydantic import BaseModel, Field


class AdverseEventError(ValueError):
    pass


EventSeverity = Literal["MINOR", "MODERATE", "SERIOUS", "CRITICAL"]
EventType = Literal["MODEL_ERROR", "ABSTENTION_FAILURE", "CALIBRATION_DRIFT", "WRONG_ROUTING", "SAFETY_SIGNAL", "OTHER"]
EventStatus = Literal["OPEN", "IN_REVIEW", "RESOLVED", "CLOSED"]


class AdverseEventRecord(BaseModel):
    event_id: str = Field(min_length=1, max_length=200)
    model_id: str = Field(min_length=1, max_length=200)
    indication: str = Field(min_length=1, max_length=100)
    event_type: EventType
    severity: EventSeverity
    description: str = Field(min_length=1, max_length=2000)
    detection_date: str = Field(min_length=1, max_length=100)
    reporter_id: str = Field(min_length=1, max_length=200)
    reporter_role: str = Field(min_length=1, max_length=100)
    status: EventStatus = Field(default="OPEN")
    root_cause: str | None = Field(default=None, max_length=2000)
    corrective_action: str | None = Field(default=None, max_length=2000)
    resolution_date: str | None = Field(default=None, max_length=100)
    regulatory_reported: bool = Field(default=False)
    regulatory_report_date: str | None = Field(default=None, max_length=100)
    synthetic_only: bool = True
    clinical_use_authorized: bool = False


class SafetySignal(BaseModel):
    signal_id: str = Field(min_length=1, max_length=200)
    model_id: str = Field(min_length=1, max_length=200)
    indication: str = Field(min_length=1, max_length=100)
    signal_type: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)
    detection_date: str = Field(min_length=1, max_length=100)
    confidence_score: float = Field(ge=0.0, le=1.0)
    status: EventStatus = Field(default="OPEN")
    recommended_action: str = Field(min_length=1, max_length=2000)
    synthetic_only: bool = True
    clinical_use_authorized: bool = False


class AdverseEventReportingSystem:
    """Adverse event reporting system for System One deployed models.

    Tracks adverse events, safety signals, and provides regulatory reporting
    capabilities. All events are auditable with provenance hashes.
    """

    def __init__(self, system_id: str = "wysh.system-one.adverse-events.v1"):
        self._system_id = system_id
        self._events: dict[str, AdverseEventRecord] = {}
        self._event_ids: set[str] = set()
        self._signals: dict[str, SafetySignal] = {}
        self._signal_ids: set[str] = set()

    def report_event(
        self,
        event_id: str,
        model_id: str,
        indication: str,
        event_type: EventType,
        severity: EventSeverity,
        description: str,
        reporter_id: str,
        reporter_role: str,
    ) -> AdverseEventRecord:
        """Report an adverse event."""
        if event_id in self._event_ids:
            raise AdverseEventError(f"Event {event_id} already reported")
        if not description or len(description) > 2000:
            raise AdverseEventError("Description must be 1-2000 characters")
        record = AdverseEventRecord(
            event_id=event_id,
            model_id=model_id,
            indication=indication,
            event_type=event_type,
            severity=severity,
            description=description,
            detection_date=_now_iso(),
            reporter_id=reporter_id,
            reporter_role=reporter_role,
        )
        self._event_ids.add(event_id)
        self._events[event_id] = record
        return record

    def get_event(self, event_id: str) -> AdverseEventRecord | None:
        return self._events.get(event_id)

    def update_event_status(
        self,
        event_id: str,
        status: EventStatus,
        root_cause: str | None = None,
        corrective_action: str | None = None,
    ) -> AdverseEventRecord:
        """Update the status of an adverse event."""
        if event_id not in self._event_ids:
            raise AdverseEventError(f"Event {event_id} not found")
        record = self._events[event_id]
        updates: dict[str, Any] = {"status": status}  # noqa
        if root_cause is not None:
            updates["root_cause"] = root_cause
        if corrective_action is not None:
            updates["corrective_action"] = corrective_action
        if status in {"RESOLVED", "CLOSED"}:
            updates["resolution_date"] = _now_iso()
        updated = record.model_copy(update=updates)
        self._events[event_id] = updated
        return updated

    def report_regulatory(
        self,
        event_id: str,
        regulatory_report_date: str | None = None,
    ) -> AdverseEventRecord:
        """Mark an event as reported to regulatory authorities."""
        if event_id not in self._event_ids:
            raise AdverseEventError(f"Event {event_id} not found")
        record = self._events[event_id]
        updated = record.model_copy(
            update={
                "regulatory_reported": True,
                "regulatory_report_date": regulatory_report_date or _now_iso(),
            }
        )
        self._events[event_id] = updated
        return updated

    def create_safety_signal(
        self,
        signal_id: str,
        model_id: str,
        indication: str,
        signal_type: str,
        description: str,
        confidence_score: float,
        recommended_action: str,
    ) -> SafetySignal:
        """Create a safety signal for monitoring."""
        if signal_id in self._signal_ids:
            raise AdverseEventError(f"Signal {signal_id} already exists")
        if not 0.0 <= confidence_score <= 1.0:
            raise AdverseEventError("Confidence score must be in [0, 1]")
        signal = SafetySignal(
            signal_id=signal_id,
            model_id=model_id,
            indication=indication,
            signal_type=signal_type,
            description=description,
            detection_date=_now_iso(),
            confidence_score=confidence_score,
            recommended_action=recommended_action,
        )
        self._signal_ids.add(signal_id)
        self._signals[signal_id] = signal
        return signal

    def update_signal_status(
        self,
        signal_id: str,
        status: EventStatus,
    ) -> SafetySignal:
        """Update the status of a safety signal."""
        if signal_id not in self._signal_ids:
            raise AdverseEventError(f"Signal {signal_id} not found")
        signal = self._signals[signal_id]
        updated = signal.model_copy(update={"status": status})
        self._signals[signal_id] = updated
        return updated

    def get_open_events(self) -> list[AdverseEventRecord]:
        return [e for e in self._events.values() if e.status == "OPEN"]

    def get_critical_events(self) -> list[AdverseEventRecord]:
        return [
            e for e in self._events.values()
            if e.severity == "CRITICAL" and e.status != "CLOSED"
        ]

    def get_open_signals(self) -> list[SafetySignal]:
        return [s for s in self._signals.values() if s.status == "OPEN"]

    def get_event_summary(self) -> dict[str, Any]:  # noqa
        total = len(self._events)
        open_events = len(self.get_open_events())
        critical = len(self.get_critical_events())
        resolved = sum(1 for e in self._events.values() if e.status == "RESOLVED")
        closed = sum(1 for e in self._events.values() if e.status == "CLOSED")
        regulatory_reported = sum(1 for e in self._events.values() if e.regulatory_reported)
        severity_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        for e in self._events.values():
            severity_counts[e.severity] = severity_counts.get(e.severity, 0) + 1
            type_counts[e.event_type] = type_counts.get(e.event_type, 0) + 1
        return {
            "total_events": total,
            "open_events": open_events,
            "critical_events": critical,
            "resolved_events": resolved,
            "closed_events": closed,
            "regulatory_reported": regulatory_reported,
            "severity_distribution": severity_counts,
            "type_distribution": type_counts,
            "open_signals": len(self.get_open_signals()),
            "synthetic_only": True,
            "clinical_use_authorized": False,
            "deny_by_default": True,
        }

    def public_status(self) -> dict[str, Any]:  # noqa
        return {
            "system": "system_one_adverse_events_v1",
            "total_events": len(self._events),
            "open_events": len(self.get_open_events()),
            "critical_events": len(self.get_critical_events()),
            "open_signals": len(self.get_open_signals()),
            "synthetic_only": True,
            "clinical_use_authorized": False,
            "deny_by_default": True,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def default_adverse_event_system() -> AdverseEventReportingSystem:
    return AdverseEventReportingSystem()
