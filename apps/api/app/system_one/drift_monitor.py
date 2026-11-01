"""System One post-market drift monitoring module.

Phase 5 — Post-Market Surveillance. Detects feature drift and model performance
drift in deployed System One decision models using Population Stability Index
(PSI) and calibration tracking. Triggers retraining review when drift exceeds
configured thresholds.

Synthetic-only: no PHI accepted, clinical use not authorized. All drift
evaluations are auditable with provenance hashes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class DriftError(ValueError):
    pass


@dataclass(frozen=True)
class DriftConfig:
    psi_threshold: float = 0.2
    calibration_threshold: float = 0.05
    min_reference_n: int = 30
    min_current_n: int = 30
    retraining_trigger_enabled: bool = True
    synthetic_only: bool = True
    clinical_use_authorized: bool = False


class DriftResult(BaseModel):
    feature_name: str
    reference_mean: float
    reference_std: float
    current_mean: float
    current_std: float
    psi: float
    drift_status: str  # "STABLE", "DRIFT", "INSUFFICIENT_SAMPLE", "INVALID_DATA"
    drift_detected: bool


class CalibrationDriftResult(BaseModel):
    model_id: str
    indication: str
    reference_ece: float
    current_ece: float
    ece_delta: float
    drift_status: str
    drift_detected: bool


class RetrainingTriggerResult(BaseModel):
    model_id: str
    indication: str
    trigger_activated: bool
    reasons: list[str]
    recommended_action: str  # "NO_ACTION", "RETRAINING_REVIEW_REQUIRED"
    timestamp: str


class SystemOneDriftMonitor:
    """Drift monitoring for System One deployed decision models.

    Uses Population Stability Index (PSI) for feature drift and Expected
    Calibration Error (ECE) delta for calibration drift. Triggers retraining
    review when thresholds are exceeded.
    """

    def __init__(self, config: DriftConfig | None = None):
        self._config = config or DriftConfig()
        self._drift_history: list[dict[str, Any]] = []

    def _bin_data(self, values: list[float], n_bins: int = 10) -> list[float]:
        """Compute histogram bin proportions for PSI calculation."""
        if not values:
            return []
        lo, hi = min(values), max(values)
        if hi <= lo:
            return [1.0] + [0.0] * (n_bins - 1)
        bin_width = (hi - lo) / n_bins
        counts = [0] * n_bins
        for v in values:
            idx = min(n_bins - 1, int((v - lo) / bin_width))
            counts[idx] += 1
        total = len(values)
        return [c / total for c in counts]

    def _psi(self, reference: list[float], current: list[float], n_bins: int = 10) -> float:
        """Compute Population Stability Index between two distributions.

        Uses shared binning based on the combined min/max of both distributions
        to ensure consistent bin edges across both samples.
        """
        if not reference or not current:
            return 0.0
        all_values = reference + current
        lo, hi = min(all_values), max(all_values)
        if hi <= lo:
            return 0.0
        bin_width = (hi - lo) / n_bins

        def hist(values: list[float]) -> list[float]:
            counts = [0] * n_bins
            for v in values:
                idx = min(n_bins - 1, int((v - lo) / bin_width))
                counts[idx] += 1
            total = len(values)
            return [c / total for c in counts]

        ref_hist = hist(reference)
        cur_hist = hist(current)
        psi = 0.0
        for r, c in zip(ref_hist, cur_hist):
            r_safe = max(r, 1e-6)
            c_safe = max(c, 1e-6)
            psi += (c_safe - r_safe) * math.log(c_safe / r_safe)
        return psi

    def _ece(self, probabilities: list[float], labels: list[int], n_bins: int = 10) -> float | None:
        """Expected Calibration Error."""
        if len(probabilities) != len(labels) or not probabilities:
            return None
        bin_boundaries = [i / n_bins for i in range(n_bins + 1)]
        ece = 0.0
        total = len(probabilities)
        for i in range(n_bins):
            bin_lo = bin_boundaries[i]
            bin_hi = bin_boundaries[i + 1]
            idxs = [
                j for j in range(total)
                if bin_lo <= probabilities[j] < bin_hi
                or (i == n_bins - 1 and probabilities[j] <= bin_hi)
            ]
            if not idxs:
                continue
            bin_acc = sum(labels[j] for j in idxs) / len(idxs)
            bin_conf = sum(probabilities[j] for j in idxs) / len(idxs)
            bin_w = len(idxs) / total
            ece += bin_w * abs(bin_conf - bin_acc)
        return ece

    def evaluate_feature_drift(
        self,
        feature_name: str,
        reference_values: list[float],
        current_values: list[float],
    ) -> DriftResult:
        """Evaluate drift for a single feature using PSI."""
        if len(reference_values) < self._config.min_reference_n:
            return DriftResult(
                feature_name=feature_name,
                reference_mean=0.0,
                reference_std=0.0,
                current_mean=0.0,
                current_std=0.0,
                psi=0.0,
                drift_status="INSUFFICIENT_SAMPLE",
                drift_detected=False,
            )
        if len(current_values) < self._config.min_current_n:
            return DriftResult(
                feature_name=feature_name,
                reference_mean=0.0,
                reference_std=0.0,
                current_mean=0.0,
                current_std=0.0,
                psi=0.0,
                drift_status="INSUFFICIENT_SAMPLE",
                drift_detected=False,
            )
        try:
            ref_mean = sum(reference_values) / len(reference_values)
            ref_var = sum((v - ref_mean) ** 2 for v in reference_values) / len(reference_values)
            ref_std = math.sqrt(max(ref_var, 0.0))
            cur_mean = sum(current_values) / len(current_values)
            cur_var = sum((v - cur_mean) ** 2 for v in current_values) / len(current_values)
            cur_std = math.sqrt(max(cur_var, 0.0))
        except (TypeError, ValueError):
            return DriftResult(
                feature_name=feature_name,
                reference_mean=0.0,
                reference_std=0.0,
                current_mean=0.0,
                current_std=0.0,
                psi=0.0,
                drift_status="INVALID_DATA",
                drift_detected=False,
            )
        psi = self._psi(reference_values, current_values)
        drift_detected = psi >= self._config.psi_threshold
        drift_status = "DRIFT" if drift_detected else "STABLE"
        return DriftResult(
            feature_name=feature_name,
            reference_mean=round(ref_mean, 6),
            reference_std=round(ref_std, 6),
            current_mean=round(cur_mean, 6),
            current_std=round(cur_std, 6),
            psi=round(psi, 6),
            drift_status=drift_status,
            drift_detected=drift_detected,
        )

    def evaluate_calibration_drift(
        self,
        model_id: str,
        indication: str,
        reference_probabilities: list[float],
        reference_labels: list[int],
        current_probabilities: list[float],
        current_labels: list[int],
    ) -> CalibrationDriftResult:
        """Evaluate calibration drift using ECE delta."""
        ref_ece = self._ece(reference_probabilities, reference_labels)
        cur_ece = self._ece(current_probabilities, current_labels)
        if ref_ece is None or cur_ece is None:
            return CalibrationDriftResult(
                model_id=model_id,
                indication=indication,
                reference_ece=0.0,
                current_ece=0.0,
                ece_delta=0.0,
                drift_status="INSUFFICIENT_SAMPLE",
                drift_detected=False,
            )
        ece_delta = abs(cur_ece - ref_ece)
        drift_detected = ece_delta >= self._config.calibration_threshold
        drift_status = "DRIFT" if drift_detected else "STABLE"
        return CalibrationDriftResult(
            model_id=model_id,
            indication=indication,
            reference_ece=round(ref_ece, 6),
            current_ece=round(cur_ece, 6),
            ece_delta=round(ece_delta, 6),
            drift_status=drift_status,
            drift_detected=drift_detected,
        )

    def evaluate_retraining_trigger(
        self,
        model_id: str,
        indication: str,
        feature_drift_results: list[DriftResult],
        calibration_drift_result: CalibrationDriftResult | None = None,
    ) -> RetrainingTriggerResult:
        """Determine whether retraining review should be triggered."""
        reasons: list[str] = []
        trigger_activated = False

        for result in feature_drift_results:
            if result.drift_detected:
                trigger_activated = True
                reasons.append(
                    f"Feature drift detected: {result.feature_name} (PSI={result.psi})"
                )

        if calibration_drift_result and calibration_drift_result.drift_detected:
            trigger_activated = True
            reasons.append(
                f"Calibration drift detected: ECE delta={calibration_drift_result.ece_delta}"
            )

        if not self._config.retraining_trigger_enabled:
            trigger_activated = False
            reasons = ["Retraining trigger disabled by configuration"]

        recommended_action = (
            "RETRAINING_REVIEW_REQUIRED" if trigger_activated else "NO_ACTION"
        )
        return RetrainingTriggerResult(
            model_id=model_id,
            indication=indication,
            trigger_activated=trigger_activated,
            reasons=reasons,
            recommended_action=recommended_action,
            timestamp=_now_iso(),
        )

    def record_drift_evaluation(
        self,
        model_id: str,
        indication: str,
        feature_results: list[DriftResult],
        calibration_result: CalibrationDriftResult | None,
        retraining_result: RetrainingTriggerResult,
    ) -> dict[str, Any]:
        """Record a drift evaluation for audit trail."""
        record = {
            "schema_version": "system-one-drift-eval-v1",
            "model_id": model_id,
            "indication": indication,
            "timestamp": _now_iso(),
            "feature_drift": [
                {
                    "feature_name": r.feature_name,
                    "psi": r.psi,
                    "drift_status": r.drift_status,
                    "drift_detected": r.drift_detected,
                }
                for r in feature_results
            ],
            "calibration_drift": (
                {
                    "reference_ece": calibration_result.reference_ece,
                    "current_ece": calibration_result.current_ece,
                    "ece_delta": calibration_result.ece_delta,
                    "drift_status": calibration_result.drift_status,
                    "drift_detected": calibration_result.drift_detected,
                }
                if calibration_result else None
            ),
            "retraining_trigger": {
                "trigger_activated": retraining_result.trigger_activated,
                "reasons": retraining_result.reasons,
                "recommended_action": retraining_result.recommended_action,
            },
            "synthetic_only": self._config.synthetic_only,
            "clinical_use_authorized": self._config.clinical_use_authorized,
        }
        record["record_sha256"] = _hash_value(record)
        self._drift_history.append(record)
        return record

    def get_drift_history(self) -> list[dict[str, Any]]:
        return list(self._drift_history)

    def public_status(self) -> dict[str, Any]:
        return {
            "monitor": "system_one_drift_v1",
            "psi_threshold": self._config.psi_threshold,
            "calibration_threshold": self._config.calibration_threshold,
            "min_reference_n": self._config.min_reference_n,
            "min_current_n": self._config.min_current_n,
            "retraining_trigger_enabled": self._config.retraining_trigger_enabled,
            "evaluations_recorded": len(self._drift_history),
            "synthetic_only": self._config.synthetic_only,
            "clinical_use_authorized": self._config.clinical_use_authorized,
            "deny_by_default": True,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash_value(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def default_drift_config() -> DriftConfig:
    return DriftConfig(
        psi_threshold=0.2,
        calibration_threshold=0.05,
        min_reference_n=30,
        min_current_n=30,
        retraining_trigger_enabled=True,
        synthetic_only=True,
        clinical_use_authorized=False,
    )
