"""Probabilistic routing engine for System One decision models.

Selects the appropriate decision model by indication, applies a confidence-
weighted routing policy, and maintains a bounded fallback chain. All routing
decisions are deterministic given the same input; there is no conversational
generation and no external provider call on the hot path.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Literal

from .decision_model import DecisionAction, ModelInferenceError, SystemOneDecisionModel
from .feature_extractor import FeatureVector, required_metrics_for


class RoutingError(ValueError):
    pass


@dataclass(frozen=True)
class RouteAttempt:
    model_id: str
    model_path: str
    status: Literal["skipped", "failure", "success"]
    reason: str | None = None
    latency_ms: int = 0


@dataclass(frozen=True)
class RoutingResult:
    indication: str
    selected_model: str | None
    selected_action: DecisionAction | None
    confidence: float | None
    abstained: bool
    abstention_reason: str | None
    route_attempts: tuple[RouteAttempt, ...]
    missing_required_metrics: tuple[str, ...]
    model_path: str | None = None


INDICATION_MODEL_MAP = {
    "diabetes": "wysh.synthetic.diabetes.review.v1",
    "hypertension": "wysh.synthetic.hypertension.review.v1",
    "chronic_kidney_disease": "wysh.synthetic.ckd.review.v1",
}

FALLBACK_CHAIN = ("wysh.synthetic.diabetes.review.v1", "wysh.synthetic.hypertension.review.v1", "wysh.synthetic.ckd.review.v1")


class RoutingEngine:
    """Selects and invokes decision models with a bounded fallback chain."""

    def __init__(self, decision_model: SystemOneDecisionModel):
        self._decision_model = decision_model

    def _model_for_indication(self, indication: str) -> str | None:
        return INDICATION_MODEL_MAP.get(indication)

    def _missing_metrics(self, indication: str, feature_vector: FeatureVector) -> tuple[str, ...]:
        name_to_value = dict(zip(feature_vector.feature_names, feature_vector.values))
        missing: list[str] = []
        for metric in required_metrics_for(indication):
            count = name_to_value.get(f"{metric}_count", 0.0)
            if count <= 0:
                missing.append(metric)
        return tuple(missing)

    def route(
        self,
        indication: str,
        feature_vector: FeatureVector,
    ) -> RoutingResult:
        missing = self._missing_metrics(indication, feature_vector)
        model_id = self._model_for_indication(indication)
        attempts: list[RouteAttempt] = []

        if model_id is None:
            return RoutingResult(
                indication=indication,
                selected_model=None,
                selected_action=None,
                confidence=None,
                abstained=True,
                abstention_reason=f"no decision model registered for indication: {indication}",
                route_attempts=tuple(attempts),
                missing_required_metrics=missing,
            )

        primary_action, primary_confidence, primary_reason, model_path = self._try_model(model_id, indication, feature_vector, attempts)
        if primary_action is not None:
            return RoutingResult(
                indication=indication,
                selected_model=model_id,
                selected_action=primary_action,
                confidence=primary_confidence,
                abstained=False,
                abstention_reason=None,
                route_attempts=tuple(attempts),
                missing_required_metrics=missing,
                model_path=model_path,
            )

        for fallback_id in FALLBACK_CHAIN:
            if fallback_id == model_id:
                continue
            fallback_action, fallback_confidence, fallback_reason, fallback_path = self._try_model(fallback_id, indication, feature_vector, attempts)
            if fallback_action is not None:
                return RoutingResult(
                    indication=indication,
                    selected_model=fallback_id,
                    selected_action=fallback_action,
                    confidence=fallback_confidence,
                    abstained=False,
                    abstention_reason=None,
                    route_attempts=tuple(attempts),
                    missing_required_metrics=missing,
                    model_path=fallback_path,
                )

        return RoutingResult(
            indication=indication,
            selected_model=model_id,
            selected_action=None,
            confidence=None,
            abstained=True,
            abstention_reason=primary_reason or "all routing attempts abstained",
            route_attempts=tuple(attempts),
            missing_required_metrics=missing,
        )

    def _try_model(self, model_id: str, indication: str, feature_vector: FeatureVector, attempts: list[RouteAttempt]) -> tuple[DecisionAction | None, float | None, str | None, str | None]:
        started = time.perf_counter()
        try:
            action, confidence, reason, model_path = self._decision_model.predict(model_id, indication, feature_vector)
            attempts.append(RouteAttempt(model_id=model_id, model_path=model_path, status="success", reason=reason, latency_ms=int((time.perf_counter() - started) * 1000)))
            return action, confidence, reason, model_path
        except ModelInferenceError as exc:
            attempts.append(RouteAttempt(model_id=model_id, model_path="threshold_rules", status="failure", reason=str(exc), latency_ms=int((time.perf_counter() - started) * 1000)))
            return None, None, str(exc), None
        except Exception as exc:  # noqa: BLE001 - routing must never crash the hot path
            attempts.append(RouteAttempt(model_id=model_id, model_path="threshold_rules", status="failure", reason=f"unexpected inference failure: {type(exc).__name__}", latency_ms=int((time.perf_counter() - started) * 1000)))
            return None, None, f"unexpected inference failure: {type(exc).__name__}", None
