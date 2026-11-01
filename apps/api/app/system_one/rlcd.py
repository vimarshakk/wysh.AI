"""System One RLCD: Reinforcement Learning for Calibrated Decisions.

Phase 1 prototype. Provides calibration for decision model outputs so that
confidence probabilities are mathematically honest:

- Temperature scaling for probability calibration
- Confidence threshold for automatic human handoff (e.g., <0.85)
- Reward function penalizing overconfidence on wrong answers
- Expected Calibration Error (ECE) monitoring
- Clinical safety reviewer reward model interface

All calibration is deterministic and auditable. No clinical use authorization
is implied by calibration output.
"""

from __future__ import annotations

from dataclasses import dataclass, field  # noqa
from hashlib import sha256  # noqa
import json  # noqa
from math import exp
from pathlib import Path  # noqa
from typing import Literal  # noqa

from pydantic import BaseModel, Field


class RLCDError(ValueError):
    pass


class CalibrationRecord(BaseModel):
    record_id: str = Field(min_length=1, max_length=200)
    model_id: str = Field(min_length=1, max_length=200)
    head_type: str = Field(min_length=1, max_length=50)
    predicted_probability: float = Field(ge=0.0, le=1.0)
    actual_outcome: int = Field(ge=0, le=1)
    confidence: float = Field(ge=0.0, le=1.0)
    abstained: bool = False
    human_handoff: bool = False
    temperature: float = Field(gt=0.0)
    timestamp: str = Field(min_length=1, max_length=100)


@dataclass(frozen=True)
class RLCDConfig:
    temperature: float = 1.0
    abstention_threshold: float = 0.85
    overconfidence_penalty: float = 0.5
    calibration_bins: int = 10
    synthetic_only: bool = True
    clinical_use_authorized: bool = False

    def __post_init__(self) -> None:
        if not 0.0 < self.temperature:
            raise RLCDError("temperature must be > 0")
        if not 0.0 <= self.abstention_threshold <= 1.0:
            raise RLCDError("abstention_threshold must be in [0, 1]")
        if not 0.0 <= self.overconfidence_penalty:
            raise RLCDError("overconfidence_penalty must be >= 0")
        if not 5 <= self.calibration_bins <= 50:
            raise RLCDError("calibration_bins must be in [5, 50]")


class SystemOneRLCD:
    """RLCD calibration engine for System One decision outputs."""

    def __init__(self, config: RLCDConfig | None = None):
        self._config = config or RLCDConfig()
        self._records: list[CalibrationRecord] = []
        self._record_ids: set[str] = set()

    def _sigmoid(self, value: float) -> float:
        value = max(-40.0, min(40.0, value))
        return 1.0 / (1.0 + exp(-value))

    def _apply_temperature(self, logit: float) -> float:
        return self._sigmoid(logit / max(self._config.temperature, 1e-6))

    def calibrate_noul(
        self,
        record_id: str,
        model_id: str,
        raw_logit: float,
        actual_outcome: int | None = None,
    ) -> CalibrationRecord:
        """Calibrate a Noul output with temperature scaling."""
        if record_id in self._record_ids:
            raise RLCDError(f"record {record_id} already exists")
        if actual_outcome is not None and actual_outcome not in {0, 1}:
            raise RLCDError("actual_outcome must be 0 or 1")

        probability = round(self._apply_temperature(raw_logit), 6)
        confidence = round(min(abs(probability - 0.5) * 2.0, 1.0), 6)
        abstained = confidence < self._config.abstention_threshold
        human_handoff = abstained

        record = CalibrationRecord(
            record_id=record_id,
            model_id=model_id,
            head_type="noul",
            predicted_probability=probability,
            actual_outcome=actual_outcome if actual_outcome is not None else -1,
            confidence=confidence,
            abstained=abstained,
            human_handoff=human_handoff,
            temperature=self._config.temperature,
            timestamp=self._utc_now(),
        )
        self._record_ids.add(record_id)
        self._records.append(record)
        return record

    def calibrate_choice(
        self,
        record_id: str,
        model_id: str,
        option_probabilities: dict[str, float],
        selected_option: str | None,
        actual_outcome: str | None = None,
    ) -> CalibrationRecord:
        """Calibrate a Choice output."""
        if record_id in self._record_ids:
            raise RLCDError(f"record {record_id} already exists")

        best_probability = max(option_probabilities.values()) if option_probabilities else 0.0
        confidence = round(best_probability, 6)
        abstained = confidence < self._config.abstention_threshold
        human_handoff = abstained

        # Encode actual outcome as binary: 1 if selected option matched actual
        actual_binary = 1 if (actual_outcome is not None and selected_option == actual_outcome) else 0
        if actual_outcome is None:
            actual_binary = -1

        record = CalibrationRecord(
            record_id=record_id,
            model_id=model_id,
            head_type="choice",
            predicted_probability=best_probability,
            actual_outcome=actual_binary,
            confidence=confidence,
            abstained=abstained,
            human_handoff=human_handoff,
            temperature=self._config.temperature,
            timestamp=self._utc_now(),
        )
        self._record_ids.add(record_id)
        self._records.append(record)
        return record

    def reward(self, record_id: str, reviewer_correct: bool, reviewer_confidence: float) -> dict[str, object]:
        """RLCD reward signal from a clinical safety reviewer.

        Reward function:
        - Positive reward for correct, well-calibrated decisions
        - Negative reward for overconfident wrong answers (overconfidence_penalty)
        - Neutral reward for abstentions (safe default)
        """
        record = self._find_record(record_id)
        if record is None:
            raise RLCDError(f"record {record_id} not found")

        if record.abstained:
            # Abstention is safe; small neutral reward
            reward_value = 0.0
            reason = "abstained_safe_default"
        elif reviewer_correct:
            # Correct decision: reward scaled by confidence (not overconfident)
            if record.confidence > 0.95:
                # Slight penalty for extreme overconfidence even when correct
                reward_value = round(0.8 - self._config.overconfidence_penalty * 0.1, 6)
                reason = "correct_slight_overconfidence_penalty"
            else:
                reward_value = round(record.confidence, 6)
                reason = "correct_well_calibrated"
        else:
            # Wrong decision: penalize, especially if overconfident
            reward_value = round(-record.confidence * self._config.overconfidence_penalty, 6)
            reason = "incorrect_overconfidence_penalty"

        return {
            "record_id": record_id,
            "reward": reward_value,
            "reason": reason,
            "reviewer_confidence": reviewer_confidence,
            "clinical_use_authorized": False,
        }

    def expected_calibration_error(self, head_type: str | None = None) -> dict[str, object]:
        """Compute Expected Calibration Error (ECE) for calibration monitoring.

        ECE measures the gap between predicted probability and actual accuracy
        across confidence bins. Lower is better (perfect calibration = 0).
        """
        records = [
            r for r in self._records
            if head_type is None or r.head_type == head_type
        ]
        # Only use records with known actual outcomes
        labeled = [r for r in records if r.actual_outcome in {0, 1} and not r.abstained]
        if not labeled:
            return {
                "head_type": head_type or "all",
                "ece": None,
                "n_labeled": 0,
                "status": "INSUFFICIENT_SAMPLE",
                "clinical_use_authorized": False,
            }

        n_bins = self._config.calibration_bins
        bin_boundaries = [i / n_bins for i in range(n_bins + 1)]
        ece = 0.0
        bin_details: list[dict[str, object]] = []

        for i in range(n_bins):
            bin_low = bin_boundaries[i]
            bin_high = bin_boundaries[i + 1]
            bin_records = [
                r for r in labeled
                if bin_low <= r.predicted_probability < bin_high
                or (i == n_bins - 1 and r.predicted_probability <= bin_high)
            ]
            if not bin_records:
                continue
            bin_accuracy = sum(1 for r in bin_records if r.actual_outcome == 1) / len(bin_records)
            bin_confidence = sum(r.predicted_probability for r in bin_records) / len(bin_records)
            bin_weight = len(bin_records) / len(labeled)
            ece += bin_weight * abs(bin_confidence - bin_accuracy)
            bin_details.append({
                "bin": i,
                "bin_low": round(bin_low, 4),
                "bin_high": round(bin_high, 4),
                "count": len(bin_records),
                "accuracy": round(bin_accuracy, 6),
                "confidence": round(bin_confidence, 6),
            })

        return {
            "head_type": head_type or "all",
            "ece": round(ece, 6),
            "n_labeled": len(labeled),
            "n_total": len(records),
            "n_abstained": sum(1 for r in records if r.abstained),
            "n_human_handoff": sum(1 for r in records if r.human_handoff),
            "status": "CALIBRATED" if ece <= 0.05 else ("NEEDS_RECALIBRATION" if ece <= 0.15 else "POOR_CALIBRATION"),
            "bins": bin_details,
            "clinical_use_authorized": False,
        }

    def abstention_rate(self, head_type: str | None = None) -> dict[str, object]:
        records = [
            r for r in self._records
            if head_type is None or r.head_type == head_type
        ]
        if not records:
            return {
                "head_type": head_type or "all",
                "abstention_rate": None,
                "n_total": 0,
                "clinical_use_authorized": False,
            }
        abstained = sum(1 for r in records if r.abstained)
        return {
            "head_type": head_type or "all",
            "abstention_rate": round(abstained / len(records), 6),
            "n_total": len(records),
            "n_abstained": abstained,
            "n_human_handoff": sum(1 for r in records if r.human_handoff),
            "clinical_use_authorized": False,
        }

    def _find_record(self, record_id: str) -> CalibrationRecord | None:
        for record in self._records:
            if record.record_id == record_id:
                return record
        return None

    @staticmethod

    def _utc_now() -> str:  # noqa
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def public_status(self) -> dict[str, object]:
        return {
            "temperature": self._config.temperature,
            "abstention_threshold": self._config.abstention_threshold,
            "overconfidence_penalty": self._config.overconfidence_penalty,
            "calibration_bins": self._config.calibration_bins,
            "total_records": len(self._records),
            "synthetic_only": self._config.synthetic_only,
            "clinical_use_authorized": self._config.clinical_use_authorized,
        }

    def snapshot(self) -> list[dict[str, object]]:
        return [record.model_dump() for record in self._records]
