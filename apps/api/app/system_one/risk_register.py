"""System One ISO 14971 risk register.

Phase 2 prototype. Risk management file for the System One clinical AI decision
model. Tracks hazards, hazardous situations, harms, risk mitigation measures,
residual risk, and benefit-risk analysis.

All entries are auditable. Risk acceptance requires qualified reviewer sign-off;
no risk acceptance grants CLINICALLY_APPROVED status automatically.
Synthetic-only: risk analysis uses de-identified scenarios only.
"""

from __future__ import annotations

from dataclasses import dataclass  # noqa
from datetime import datetime, timezone
from hashlib import sha256  # noqa
import json  # noqa
from pathlib import Path  # noqa
from typing import Literal

from pydantic import BaseModel, Field


class RiskError(ValueError):
    pass


RiskSeverity = Literal["NEGLIGIBLE", "MINOR", "SERIOUS", "CRITICAL"]
RiskProbability = Literal["VERY_UNLIKELY", "UNLIKELY", "POSSIBLE", "LIKELY", "VERY_LIKELY"]
RiskAcceptability = Literal["ACCEPTABLE", "UNACCEPTABLE", "REVIEW_REQUIRED"]
RiskControlMeasure = Literal["INHERENT_SAFETY", "PROTECTIVE_MEASURE", "INFORMATION_FOR_SAFETY"]


class HazardRecord(BaseModel):
    hazard_id: str = Field(min_length=1, max_length=200)
    hazard_description: str = Field(min_length=1, max_length=2000)
    hazardous_situation: str = Field(min_length=1, max_length=2000)
    potential_harm: str = Field(min_length=1, max_length=2000)
    harm_severity: RiskSeverity
    initial_probability: RiskProbability
    initial_risk_level: str = Field(min_length=1, max_length=100)
    risk_control_measures: list[str] = Field(default_factory=list, max_length=50)
    control_measure_type: RiskControlMeasure | None = None
    residual_probability: RiskProbability | None = None
    residual_risk_level: str | None = Field(default=None, max_length=100)
    risk_acceptability: RiskAcceptability = "REVIEW_REQUIRED"
    benefit_risk_justification: str | None = Field(default=None, max_length=2000)
    reviewer_id: str | None = Field(default=None, max_length=200)
    reviewer_signoff_timestamp: str | None = Field(default=None, max_length=100)
    created_at: str = Field(min_length=1, max_length=100)
    updated_at: str = Field(min_length=1, max_length=100)


class SystemOneRiskRegister:
    """ISO 14971 risk management register for System One decision model."""

    def __init__(self, register_id: str = "wysh.system-one.risk-register.v1"):
        self._register_id = register_id
        self._hazards: dict[str, HazardRecord] = {}
        self._hazard_ids: set[str] = set()

    def add_hazard(self, hazard: HazardRecord) -> None:
        if hazard.hazard_id in self._hazard_ids:
            raise RiskError(f"hazard {hazard.hazard_id} already exists")
        now = self._utc_now()
        record = hazard.model_copy(update={"created_at": now, "updated_at": now})
        self._hazard_ids.add(record.hazard_id)
        self._hazards[record.hazard_id] = record

    def update_hazard(
        self,
        hazard_id: str,
        *,
        residual_probability: RiskProbability | None = None,
        residual_risk_level: str | None = None,
        risk_acceptability: RiskAcceptability | None = None,
        benefit_risk_justification: str | None = None,
        reviewer_id: str | None = None,
        reviewer_signoff: bool = False,
    ) -> HazardRecord:
        if hazard_id not in self._hazard_ids:
            raise RiskError(f"hazard {hazard_id} not found")
        record = self._hazards[hazard_id]
        updates: dict[str, object] = {"updated_at": self._utc_now()}
        if residual_probability is not None:
            updates["residual_probability"] = residual_probability
        if residual_risk_level is not None:
            updates["residual_risk_level"] = residual_risk_level
        if risk_acceptability is not None:
            updates["risk_acceptability"] = risk_acceptability
        if benefit_risk_justification is not None:
            updates["benefit_risk_justification"] = benefit_risk_justification
        if reviewer_id is not None:
            updates["reviewer_id"] = reviewer_id
        if reviewer_signoff:
            updates["reviewer_signoff_timestamp"] = self._utc_now()
        updated = record.model_copy(update=updates)
        self._hazards[hazard_id] = updated
        return updated

    def get_hazard(self, hazard_id: str) -> HazardRecord | None:
        return self._hazards.get(hazard_id)

    def list_hazards(self) -> list[HazardRecord]:
        return sorted(self._hazards.values(), key=lambda h: h.hazard_id)

    def unmitigated_count(self) -> int:
        return sum(1 for h in self._hazards.values() if h.risk_acceptability != "ACCEPTABLE")

    def critical_count(self) -> int:
        return sum(
            1 for h in self._hazards.values()
            if h.harm_severity == "CRITICAL" and h.risk_acceptability != "ACCEPTABLE"
        )

    def public_status(self) -> dict[str, object]:
        return {
            "register_id": self._register_id,
            "total_hazards": len(self._hazards),
            "unmitigated_hazards": self.unmitigated_count(),
            "critical_unmitigated": self.critical_count(),
            "synthetic_only": True,
            "clinical_use_authorized": False,
            "deny_by_default": True,
            "standard": "ISO 14971",
        }

    def snapshot(self) -> list[dict[str, object]]:
        return [hazard.model_dump() for hazard in self._hazards.values()]

    @staticmethod

    def _utc_now() -> str:  # noqa
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
