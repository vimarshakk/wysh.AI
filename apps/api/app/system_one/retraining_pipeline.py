"""System One continuous retraining trigger pipeline.

Phase 5 — Post-Market Surveillance. Combines drift monitoring, surveillance
data, and adverse events to trigger retraining reviews for deployed System One
decision models.

Synthetic-only: no PHI accepted, clinical use not authorized. All triggers
are auditable with provenance hashes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

from pydantic import BaseModel, Field


class RetrainingTriggerError(ValueError):
    pass


@dataclass(frozen=True)
class RetrainingTriggerConfig:
    drift_psi_threshold: float = 0.2
    calibration_ece_delta_threshold: float = 0.05
    adverse_event_rate_threshold: float = 0.05
    min_inferences_for_trigger: int = 100
    auto_trigger_retraining: bool = False
    synthetic_only: bool = True
    clinical_use_authorized: bool = False


class RetrainingTriggerEvent(BaseModel):
    trigger_id: str = Field(min_length=1, max_length=200)
    model_id: str = Field(min_length=1, max_length=200)
    indication: str = Field(min_length=1, max_length=100)
    trigger_type: str = Field(min_length=1, max_length=100)  # "DRIFT", "CALIBRATION", "ADVERSE_EVENT", "SCHEDULED"
    severity: str = Field(min_length=1, max_length=50)  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    description: str = Field(min_length=1, max_length=2000)
    detection_date: str = Field(min_length=1, max_length=100)
    status: str = Field(default="OPEN")  # "OPEN", "IN_REVIEW", "APPROVED", "REJECTED", "COMPLETED"
    retraining_recommended: bool = False
    retraining_completed: bool = False
    completion_date: str | None = Field(default=None, max_length=100)
    synthetic_only: bool = True
    clinical_use_authorized: bool = False


class RetrainingPipeline:
    """Continuous retraining trigger pipeline for System One models.

    Combines drift monitoring results, surveillance alerts, and adverse events
    to trigger retraining reviews.
    """

    def __init__(self, config: RetrainingTriggerConfig | None = None):
        self._config = config or RetrainingTriggerConfig()
        self._triggers: dict[str, RetrainingTriggerEvent] = {}
        self._trigger_ids: set[str] = set()

    def create_trigger(
        self,
        trigger_id: str,
        model_id: str,
        indication: str,
        trigger_type: str,
        severity: str,
        description: str,
        retraining_recommended: bool = False,
    ) -> RetrainingTriggerEvent:
        """Create a retraining trigger event."""
        if trigger_id in self._trigger_ids:
            raise RetrainingTriggerError(f"Trigger {trigger_id} already exists")
        if severity not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            raise RetrainingTriggerError("Severity must be LOW, MEDIUM, HIGH, or CRITICAL")
        event = RetrainingTriggerEvent(
            trigger_id=trigger_id,
            model_id=model_id,
            indication=indication,
            trigger_type=trigger_type,
            severity=severity,
            description=description,
            detection_date=_now_iso(),
            retraining_recommended=retraining_recommended,
        )
        self._trigger_ids.add(trigger_id)
        self._triggers[trigger_id] = event
        return event

    def evaluate_drift_trigger(
        self,
        trigger_id: str,
        model_id: str,
        indication: str,
        psi: float,
        ece_delta: float,
    ) -> RetrainingTriggerEvent:
        """Evaluate whether drift metrics warrant a retraining trigger."""
        reasons: list[str] = []
        if psi >= self._config.drift_psi_threshold:
            reasons.append(f"Feature drift PSI={psi} >= threshold={self._config.drift_psi_threshold}")
        if ece_delta >= self._config.calibration_ece_delta_threshold:
            reasons.append(f"Calibration drift ECE delta={ece_delta} >= threshold={self._config.calibration_ece_delta_threshold}")
        if not reasons:
            return RetrainingTriggerEvent(
                trigger_id=trigger_id,
                model_id=model_id,
                indication=indication,
                trigger_type="DRIFT",
                severity="LOW",
                description="No significant drift detected",
                detection_date=_now_iso(),
                retraining_recommended=False,
            )
        severity_level = "HIGH" if psi >= 0.3 or ece_delta >= 0.1 else "MEDIUM"
        return RetrainingTriggerEvent(
            trigger_id=trigger_id,
            model_id=model_id,
            indication=indication,
            trigger_type="DRIFT",
            severity=severity_level,
            description="; ".join(reasons),
            detection_date=_now_iso(),
            retraining_recommended=True,
        )

    def evaluate_adverse_event_trigger(
        self,
        trigger_id: str,
        model_id: str,
        indication: str,
        total_inferences: int,
        adverse_event_count: int,
    ) -> RetrainingTriggerEvent:
        """Evaluate whether adverse event rate warrants a retraining trigger."""
        if total_instances := total_inferences:
            event_rate = adverse_event_count / total_instances
        else:
            event_rate = 0.0
        if event_rate < self._config.adverse_event_rate_threshold:
            return RetrainingTriggerEvent(
                trigger_id=trigger_id,
                model_id=model_id,
                indication=indication,
                trigger_type="ADVERSE_EVENT",
                severity="LOW",
                description=f"Adverse event rate={event_rate} below threshold={self._config.adverse_event_rate_threshold}",
                detection_date=_now_iso(),
                retraining_recommended=False,
            )
        severity_level = "CRITICAL" if event_rate >= 0.1 else "HIGH"
        return RetrainingTriggerEvent(
            trigger_id=trigger_id,
            model_id=model_id,
            indication=indication,
            trigger_type="ADVERSE_EVENT",
            severity=severity_level,
            description=f"Adverse event rate={event_rate} >= threshold={self._config.adverse_event_rate_threshold}",
            detection_date=_now_iso(),
            retraining_recommended=True,
        )

    def get_trigger(self, trigger_id: str) -> RetrainingTriggerEvent | None:
        return self._triggers.get(trigger_id)

    def update_trigger_status(
        self,
        trigger_id: str,
        status: str,
        retraining_completed: bool = False,
        completion_date: str | None = None,
    ) -> RetrainingTriggerEvent:
        """Update the status of a retraining trigger."""
        if trigger_id not in self._trigger_ids:
            raise RetrainingTriggerError(f"Trigger {trigger_id} not found")
        if status not in {"OPEN", "IN_REVIEW", "APPROVED", "REJECTED", "COMPLETED"}:
            raise RetrainingTriggerError("Invalid status")
        event = self._triggers[trigger_id]
        updates: dict[str, Any] = {"status": status}
        if retraining_completed:
            updates["retraining_completed"] = True
            updates["completion_date"] = completion_date or _now_iso()
        updated = event.model_copy(update=updates)
        self._triggers[trigger_id] = updated
        return updated

    def get_open_triggers(self) -> list[RetrainingTriggerEvent]:
        return [t for t in self._triggers.values() if t.status == "OPEN"]

    def get_pending_retraining(self) -> list[RetrainingTriggerEvent]:
        return [
            t for t in self._triggers.values()
            if t.retraining_recommended and t.status in {"OPEN", "IN_REVIEW", "APPROVED"}
        ]

    def get_trigger_summary(self) -> dict[str, Any]:
        total = len(self._triggers)
        open_triggers = len(self.get_open_triggers())
        pending = len(self.get_pending_retraining())
        completed = sum(1 for t in self._triggers.values() if t.status == "COMPLETED")
        severity_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        for t in self._triggers.values():
            severity_counts[t.severity] = severity_counts.get(t.severity, 0) + 1
            type_counts[t.trigger_type] = type_counts.get(t.trigger_type, 0) + 1
        return {
            "total_triggers": total,
            "open_triggers": open_triggers,
            "pending_retraining": pending,
            "completed_triggers": completed,
            "severity_distribution": severity_counts,
            "type_distribution": type_counts,
            "synthetic_only": True,
            "clinical_use_authorized": False,
            "deny_by_default": True,
        }

    def public_status(self) -> dict[str, Any]:
        return {
            "pipeline": "system_one_retraining_v1",
            "total_triggers": len(self._triggers),
            "open_triggers": len(self.get_open_triggers()),
            "pending_retraining": len(self.get_pending_retraining()),
            "drift_psi_threshold": self._config.drift_psi_threshold,
            "calibration_ece_delta_threshold": self._config.calibration_ece_delta_threshold,
            "adverse_event_rate_threshold": self._config.adverse_event_rate_threshold,
            "min_inferences_for_trigger": self._config.min_inferences_for_trigger,
            "auto_trigger_retraining": self._config.auto_trigger_retraining,
            "synthetic_only": self._config.synthetic_only,
            "clinical_use_authorized": self._config.clinical_use_authorized,
            "deny_by_default": True,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash_value(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def default_retraining_config() -> RetrainingTriggerConfig:
    return RetrainingTriggerConfig(
        drift_psi_threshold=0.2,
        calibration_ece_delta_threshold=0.05,
        adverse_event_rate_threshold=0.05,
        min_inferences_for_trigger=100,
        auto_trigger_retraining=False,
        synthetic_only=True,
        clinical_use_authorized=False,
    )
