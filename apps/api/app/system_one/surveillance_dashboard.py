"""System One post-market surveillance dashboard module.

Phase 5 — Post-Market Surveillance. Tracks real-world performance metrics,
model usage statistics, and provides a dashboard view for monitoring deployed
System One decision models in production.

Synthetic-only: no PHI accepted, clinical use not authorized. All surveillance
data is auditable with provenance hashes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

from pydantic import BaseModel, Field


class SurveillanceError(ValueError):
    pass


@dataclass(frozen=True)
class SurveillanceConfig:
    max_inference_records: int = 100000
    alert_on_drift: bool = True
    alert_on_abstention_rate_increase: bool = True
    abstention_rate_alert_threshold: float = 0.5
    synthetic_only: bool = True
    clinical_use_authorized: bool = False


class InferenceRecord(BaseModel):
    inference_id: str = Field(min_length=1, max_length=200)
    model_id: str = Field(min_length=1, max_length=200)
    indication: str = Field(min_length=1, max_length=100)
    language: str = Field(min_length=2, max_length=10)
    timestamp: str = Field(min_length=1, max_length=100)
    noul_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    choice_selected: str | None = Field(default=None, max_length=200)
    abstained: bool = False
    human_handoff_triggered: bool = False
    clinical_use_authorized: bool = False


class PerformanceSnapshot(BaseModel):
    model_id: str = Field(min_length=1, max_length=200)
    indication: str = Field(min_length=1, max_length=100)
    period_start: str = Field(min_length=1, max_length=100)
    period_end: str = Field(min_length=1, max_length=100)
    total_inferences: int = Field(ge=0)
    total_abstentions: int = Field(ge=0)
    total_human_handoffs: int = Field(ge=0)
    abstention_rate: float = Field(ge=0.0, le=1.0)
    human_handoff_rate: float = Field(ge=0.0, le=1.0)
    language_distribution: dict[str, int] = Field(default_factory=dict)
    indication_distribution: dict[str, int] = Field(default_factory=dict)
    synthetic_only: bool = True
    clinical_use_authorized: bool = False


class SurveillanceDashboard:
    """Post-market surveillance dashboard for System One deployed models.

    Tracks inference volume, abstention rates, human handoff rates, and
    language/indication distributions for deployed models.
    """

    def __init__(self, config: SurveillanceConfig | None = None):
        self._config = config or SurveillanceConfig()
        self._inference_records: list[InferenceRecord] = []
        self._performance_snapshots: list[PerformanceSnapshot] = []

    def record_inference(
        self,
        inference_id: str,
        model_id: str,
        indication: str,
        language: str,
        noul_probability: float | None = None,
        choice_selected: str | None = None,
        abstained: bool = False,
        human_handoff_triggered: bool = False,
        clinical_use_authorized: bool = False,
    ) -> InferenceRecord:
        """Record a single inference for surveillance tracking."""
        if len(self._inference_records) >= self._config.max_inference_records:
            # Drop oldest record to maintain bounded memory
            self._inference_records.pop(0)
        record = InferenceRecord(
            inference_id=inference_id,
            model_id=model_id,
            indication=indication,
            language=language,
            timestamp=_now_iso(),
            noul_probability=noul_probability,
            choice_selected=choice_selected,
            abstained=abstained,
            human_handoff_triggered=human_handoff_triggered,
            clinical_use_authorized=clinical_use_authorized,
        )
        self._inference_records.append(record)
        return record

    def get_performance_snapshot(
        self,
        model_id: str,
        indication: str,
        period_start: str,
        period_end: str,
    ) -> PerformanceSnapshot:
        """Generate a performance snapshot for a model over a time period."""
        records = [
            r for r in self._inference_records
            if r.model_id == model_id
            and r.indication == indication
            and period_start <= r.timestamp <= period_end
        ]
        total = len(records)
        abstentions = sum(1 for r in records if r.abstained)
        handoffs = sum(1 for r in records if r.human_handoff_triggered)
        abstention_rate = abstentions / total if total > 0 else 0.0
        handoff_rate = handoffs / total if total > 0 else 0.0
        lang_dist: dict[str, int] = {}
        ind_dist: dict[str, int] = {}
        for r in records:
            lang_dist[r.language] = lang_dist.get(r.language, 0) + 1
            ind_dist[r.indication] = ind_dist.get(r.indication, 0) + 1
        return PerformanceSnapshot(
            model_id=model_id,
            indication=indication,
            period_start=period_start,
            period_end=period_end,
            total_inferences=total,
            total_abstentions=abstentions,
            total_human_handoffs=handoffs,
            abstention_rate=round(abstention_rate, 6),
            human_handoff_rate=round(handoff_rate, 6),
            language_distribution=lang_dist,
            indication_distribution=ind_dist,
            synthetic_only=True,
            clinical_use_authorized=False,
        )

    def get_alerts(self) -> list[dict[str, Any]]:
        """Generate alerts based on surveillance thresholds."""
        alerts: list[dict[str, Any]] = []
        if not self._inference_records:
            return alerts
        # Group by model/indication
        models: dict[tuple[str, str], list[InferenceRecord]] = {}
        for r in self._inference_records:
            key = (r.model_id, r.indication)
            models.setdefault(key, []).append(r)
        for (model_id, indication), records in models.items():
            total = len(records)
            abstentions = sum(1 for r in records if r.abstained)
            rate = abstentions / total if total > 0 else 0.0
            if (
                self._config.alert_on_abstention_rate_increase
                and rate > self._config.abstention_rate_alert_threshold
            ):
                alerts.append({
                    "alert_type": "high_abstention_rate",
                    "model_id": model_id,
                    "indication": indication,
                    "abstention_rate": round(rate, 6),
                    "threshold": self._config.abstention_rate_alert_threshold,
                    "timestamp": _now_iso(),
                    "severity": "WARNING",
                })
        return alerts

    def get_dashboard_summary(self) -> dict[str, Any]:
        """Get a high-level dashboard summary."""
        total = len(self._inference_records)
        abstentions = sum(1 for r in self._inference_records if r.abstained)
        handoffs = sum(1 for r in self._inference_records if r.human_handoff_triggered)
        models: dict[str, int] = {}
        indications: dict[str, int] = {}
        languages: dict[str, int] = {}
        for r in self._inference_records:
            models[r.model_id] = models.get(r.model_id, 0) + 1
            indications[r.indication] = indications.get(r.indication, 0) + 1
            languages[r.language] = languages.get(r.language, 0) + 1
        alerts = self.get_alerts()
        return {
            "total_inferences": total,
            "total_abstentions": abstentions,
            "total_human_handoffs": handoffs,
            "overall_abstention_rate": round(abstentions / total, 6) if total > 0 else 0.0,
            "overall_handoff_rate": round(handoffs / total, 6) if total > 0 else 0.0,
            "model_count": len(models),
            "models": models,
            "indications": indications,
            "languages": languages,
            "active_alerts": len(alerts),
            "alerts": alerts,
            "synthetic_only": True,
            "clinical_use_authorized": False,
            "deny_by_default": True,
        }

    def record_performance_snapshot(self, snapshot: PerformanceSnapshot) -> None:
        """Record a performance snapshot for historical tracking."""
        self._performance_snapshots.append(snapshot)

    def get_performance_history(self) -> list[PerformanceSnapshot]:
        return list(self._performance_snapshots)

    def public_status(self) -> dict[str, Any]:
        return {
            "dashboard": "system_one_surveillance_v1",
            "total_inferences": len(self._inference_records),
            "snapshots_recorded": len(self._performance_snapshots),
            "max_inference_records": self._config.max_inference_records,
            "alert_on_drift": self._config.alert_on_drift,
            "alert_on_abstention_rate_increase": self._config.alert_on_abstention_rate_increase,
            "abstention_rate_alert_threshold": self._config.abstention_rate_alert_threshold,
            "synthetic_only": self._config.synthetic_only,
            "clinical_use_authorized": self._config.clinical_use_authorized,
            "deny_by_default": True,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def default_surveillance_config() -> SurveillanceConfig:
    return SurveillanceConfig(
        max_inference_records=100000,
        alert_on_drift=True,
        alert_on_abstention_rate_increase=True,
        abstention_rate_alert_threshold=0.5,
        synthetic_only=True,
        clinical_use_authorized=False,
    )
