"""Explicit synthetic-only ML operations contracts.

This module coordinates research infrastructure; it does not promote models to
clinical use. Inputs and outputs are hashed in audit records, and missing
evidence produces an explicit blocked/insufficient state.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite, log
from typing import Any, Mapping


class MLOperationsError(ValueError):
    pass


def _hash(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass(frozen=True)
class ModelVersion:
    model_id: str
    version: str
    artifact_sha256: str
    status: str = "EXPERIMENTAL"
    traffic_weight: int = 0
    synthetic_only: bool = True
    clinical_use_authorized: bool = False


class ResearchModelRegistry:
    """Small immutable-in-use registry for local research and A/B assignment."""

    def __init__(self) -> None:
        self._versions: dict[tuple[str, str], ModelVersion] = {}

    def register(self, version: ModelVersion) -> ModelVersion:
        if not version.synthetic_only or version.clinical_use_authorized:
            raise MLOperationsError("only synthetic, non-clinical model versions may be registered")
        key = (version.model_id, version.version)
        if key in self._versions:
            raise MLOperationsError("model version is immutable and already registered")
        if not version.artifact_sha256 or len(version.artifact_sha256) != 64:
            raise MLOperationsError("artifact hash is required")
        self._versions[key] = version
        return version

    def get(self, model_id: str, version: str) -> ModelVersion:
        try:
            return self._versions[(model_id, version)]
        except KeyError as exc:
            raise MLOperationsError("model version is not registered") from exc

    def assign(self, *, subject_key: str, candidates: tuple[tuple[str, str], ...]) -> ModelVersion:
        if not subject_key or not candidates:
            raise MLOperationsError("subject key and candidates are required")
        versions = [self.get(model_id, version) for model_id, version in candidates]
        if any(item.traffic_weight < 0 for item in versions) or sum(item.traffic_weight for item in versions) != 100:
            raise MLOperationsError("A/B traffic weights must be non-negative and sum to 100")
        bucket = int(sha256(subject_key.encode()).hexdigest()[:8], 16) % 100
        cumulative = 0
        for item in versions:
            cumulative += item.traffic_weight
            if bucket < cumulative:
                return item
        raise MLOperationsError("A/B assignment failed closed")

    def snapshot(self) -> tuple[ModelVersion, ...]:
        return tuple(self._versions.values())


def summarize_validation_outcomes(labels: list[int], predictions: list[int], *, minimum_n: int = 30) -> dict[str, Any]:
    if len(labels) != len(predictions) or not labels or any(item not in {0, 1} for item in labels + predictions):
        return {"status": "INVALID_DATA"}
    if len(labels) < minimum_n or len(set(labels)) < 2:
        return {"status": "INSUFFICIENT_SAMPLE", "n": len(labels), "minimum_n": minimum_n}
    tp = sum(actual == predicted == 1 for actual, predicted in zip(labels, predictions))
    tn = sum(actual == predicted == 0 for actual, predicted in zip(labels, predictions))
    fp = sum(actual == 0 and predicted == 1 for actual, predicted in zip(labels, predictions))
    fn = sum(actual == 1 and predicted == 0 for actual, predicted in zip(labels, predictions))
    return {"status": "VALID", "n": len(labels), "tp": tp, "tn": tn, "fp": fp, "fn": fn, "sensitivity": tp / (tp + fn) if tp + fn else None, "specificity": tn / (tn + fp) if tn + fp else None, "ppv": tp / (tp + fp) if tp + fp else None, "npv": tn / (tn + fn) if tn + fn else None}


def detect_numeric_drift(reference: list[float], current: list[float], *, threshold: float = 0.2, minimum_n: int = 30) -> dict[str, Any]:
    if threshold <= 0 or minimum_n < 1:
        return {"status": "INVALID_CONFIGURATION", "retraining_triggered": False}
    if not reference or not current or any(not isfinite(float(value)) for value in reference + current):
        return {"status": "INVALID_DATA", "retraining_triggered": False}
    if len(reference) < minimum_n or len(current) < minimum_n:
        return {"status": "INSUFFICIENT_SAMPLE", "reference_n": len(reference), "current_n": len(current), "minimum_n": minimum_n, "retraining_triggered": False}
    low, high = min(reference), max(reference)
    if high <= low:
        drift = 0.0 if all(value == low for value in current) else float("inf")
    else:
        edges = [low + (high - low) * index / 5 for index in range(6)]  # noqa

        def histogram(values: list[float]) -> list[float]:
            counts = [0] * 5
            for value in values:
                index = min(4, max(0, int((value - low) / (high - low) * 5)))
                counts[index] += 1
            total = len(values)
            return [max(count / total, 1e-6) for count in counts]
        ref_hist, cur_hist = histogram(reference), histogram(current)
        drift = sum((cur - ref) * log(cur / ref) for ref, cur in zip(ref_hist, cur_hist))
    return {"status": "DRIFT" if drift >= threshold else "STABLE", "psi": drift, "threshold": threshold, "retraining_triggered": drift >= threshold, "action": "RETRAINING_REVIEW_REQUIRED" if drift >= threshold else "NO_ACTION"}


class DriftMonitor:
    """Evaluate feature drift and queue review-only retraining requests.

    The monitor never starts training, changes traffic, or promotes a model.
    Each evaluation is retained as a redacted decision record so a qualified
    reviewer can inspect the exact model/version and aggregate drift results.
    """

    def __init__(self, *, minimum_n: int = 30, threshold: float = 0.2) -> None:
        if minimum_n < 1 or threshold <= 0:
            raise MLOperationsError("drift monitor configuration is invalid")
        self.minimum_n = minimum_n
        self.threshold = threshold
        self._reviews: list[dict[str, Any]] = []
        self._evaluation_ids: set[str] = set()
        self._previous_hash = "GENESIS"

    def evaluate(self, *, model_id: str, model_version: str, reference: Mapping[str, list[float]], current: Mapping[str, list[float]], evaluation_id: str | None = None) -> dict[str, Any]:
        if evaluation_id is not None and (not evaluation_id or evaluation_id in self._evaluation_ids):
            return {"status": "REPLAY_REJECTED", "review_required": False, "clinical_use_authorized": False}
        if not model_id or not model_version or set(reference) != set(current) or not reference:
            return {"status": "INVALID_DATA", "review_required": False, "clinical_use_authorized": False}
        features = {name: detect_numeric_drift(reference[name], current[name], threshold=self.threshold, minimum_n=self.minimum_n) for name in sorted(reference)}
        invalid = any(item["status"] in {"INVALID_DATA", "INVALID_CONFIGURATION"} for item in features.values())
        insufficient = any(item["status"] == "INSUFFICIENT_SAMPLE" for item in features.values())
        drifted = any(item.get("retraining_triggered") is True for item in features.values())
        status = "INVALID_DATA" if invalid else ("INSUFFICIENT_SAMPLE" if insufficient else ("DRIFT" if drifted else "STABLE"))
        record = {"schema_version": "wysh-ai-drift-review-v1", "evaluation_id": evaluation_id, "model_id": model_id, "model_version": model_version, "status": status, "feature_count": len(features), "drifted_features": [name for name, item in features.items() if item.get("retraining_triggered")], "review_required": drifted, "action": "RETRAINING_REVIEW_REQUIRED" if drifted else "NO_ACTION", "clinical_use_authorized": False, "previous_record_sha256": self._previous_hash}
        record_hash = _hash(record)
        record["record_sha256"] = record_hash
        self._previous_hash = record_hash
        if evaluation_id is not None:
            self._evaluation_ids.add(evaluation_id)
        self._reviews.append(record)
        return {**record, "features": features}

    @property

    def review_queue(self) -> tuple[dict[str, Any], ...]:  # noqa
        return tuple(self._reviews)


def explain_linear_prediction(*, features: Mapping[str, float], weights: Mapping[str, float], intercept: float = 0.0) -> dict[str, Any]:
    contributions = [{"feature": name, "value": value, "weight": weights.get(name, 0.0), "contribution": value * weights.get(name, 0.0)} for name, value in features.items()]
    return {"status": "PASS", "explainability_type": "NATIVE_LINEAR_ATTRIBUTION", "base_value": intercept, "contributions": sorted(contributions, key=lambda item: abs(item["contribution"]), reverse=True), "shap_lime_status": "NOT_CONFIGURED", "clinical_use_authorized": False}


@dataclass(frozen=True)
class InferenceAuditRecord:
    event_id: str
    model_id: str
    model_version: str
    input_sha256: str
    output_sha256: str
    status: str
    review_required: bool
    synthetic_only: bool = True
    clinical_use_authorized: bool = False


class InferenceAuditLog:

    def __init__(self) -> None:
        self._records: list[InferenceAuditRecord] = []

    def append(self, *, event_id: str, model_id: str, model_version: str, input_payload: Any, output_payload: Any, status: str, review_required: bool = True) -> InferenceAuditRecord:
        record = InferenceAuditRecord(event_id, model_id, model_version, _hash(input_payload), _hash(output_payload), status, review_required)
        self._records.append(record)
        return record

    @property

    def records(self) -> tuple[InferenceAuditRecord, ...]:  # noqa
        return tuple(self._records)
