"""System One decision model: lightweight, deterministic, probabilistic routing.

This model performs fast structured inference on a feature vector. It does not
generate text, does not contact external providers, and does not make clinical
diagnoses. It outputs a structured routing decision with calibrated confidence
and an explicit abstention policy.

Backed by the R8B dependency-free logistic-regression baseline experiment
manifest when available; falls back to a transparent threshold rule set.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from math import exp
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .feature_extractor import FeatureVector
from .model_lifecycle import ModelLifecycleStore, REGISTRY_PATH, STATUSES


class ModelInferenceError(ValueError):
    pass


DecisionAction = Literal["review_required", "no_gap_detected", "escalate", "monitor", "abstain"]


class SystemOneDecision(BaseModel):
    decision_id: str = Field(min_length=1, max_length=200)
    indication: str = Field(min_length=1, max_length=100)
    selected_action: DecisionAction | None = None
    route: str | None = Field(default=None, max_length=100)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    abstained: bool = False
    abstention_reason: str | None = Field(default=None, max_length=500)
    model_id: str = Field(min_length=1, max_length=200)
    model_status: str = Field(min_length=1, max_length=50)
    feature_hash: str = Field(min_length=1, max_length=128)
    evidence_used: list[str] = Field(default_factory=list, max_length=500)
    missing_required_metrics: list[str] = Field(default_factory=list, max_length=50)
    human_review_required: bool = True
    clinical_use_authorized: bool = False
    latency_ms: int = Field(default=0, ge=0)
    system: Literal["system_one"] = "system_one"


@dataclass(frozen=True)
class TrainedModel:
    model_id: str
    indication: str
    algorithm: str
    intercept: float
    weights: tuple[float, ...]
    feature_names: tuple[str, ...]
    standardization: dict[str, list[float]]
    decision_threshold: float
    provenance_hash: str
    clinical_use_authorized: bool = False


def _sigmoid(value: float) -> float:
    value = max(-40.0, min(40.0, value))
    return 1.0 / (1.0 + exp(-value))


def _standardize(values: list[float], means: list[float], scales: list[float]) -> list[float]:
    return [(value - mean) / scale for value, mean, scale in zip(values, means, scales)]


class SystemOneDecisionModel:
    """Fast, deterministic decision model backed by the model registry."""

    def __init__(self, registry_path: Path | None = None):
        self._registry_path = registry_path or REGISTRY_PATH
        self._lifecycle = ModelLifecycleStore(self._registry_path)
        self._trained: dict[str, TrainedModel] = {}
        self._threshold_rules: dict[str, dict[str, object]] = {
            "diabetes": {
                "hba1c_percent": {"review_if_ge": 6.5, "escalate_if_ge": 9.0},
                "mean_glucose_mg_dl": {"review_if_ge": 126.0, "escalate_if_ge": 200.0},
            },
            "hypertension": {
                "bp_systolic_mmhg": {"review_if_ge": 130.0, "escalate_if_ge": 180.0},
                "bp_diastolic_mmhg": {"review_if_ge": 80.0, "escalate_if_ge": 120.0},
            },
            "chronic_kidney_disease": {
                "egfr_ml_min_1_73m2": {"review_if_le": 60.0, "escalate_if_le": 30.0},
                "urine_acr_mg_g": {"review_if_ge": 30.0, "escalate_if_ge": 300.0},
            },
        }

    def _load_trained(self, model_id: str) -> TrainedModel | None:
        if model_id in self._trained:
            return self._trained[model_id]
        manifest_path = Path(__file__).parents[3] / "artifacts" / "r8-test-evidence" / f"{model_id}.json"
        if not manifest_path.is_file():
            return None
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if manifest.get("schema_version") != "r8b-experiment-v1":
            return None
        model_block = manifest.get("model", {})
        standardization = model_block.get("standardization", {})
        self._trained[model_id] = TrainedModel(
            model_id=model_id,
            indication=manifest.get("label", "synthetic_review_required"),
            algorithm=manifest.get("algorithm", "dependency-free-logistic-regression"),
            intercept=float(model_block.get("intercept", 0.0)),
            weights=tuple(float(w) for w in model_block.get("weights", [])),
            feature_names=tuple(manifest.get("features", [])),
            standardization={"means": standardization.get("means", []), "scales": standardization.get("scales", [])},
            decision_threshold=0.5,
            provenance_hash=manifest.get("provenance_hash", ""),
            clinical_use_authorized=bool(manifest.get("clinical_use_authorized", False)),
        )
        return self._trained[model_id]

    def _infer_logistic(self, trained: TrainedModel, features: list[float]) -> float:
        means = trained.standardization.get("means", [])
        scales = trained.standardization.get("scales", [])
        if len(means) != len(features) or len(scales) != len(features):
            standardized = features
        else:
            standardized = _standardize(features, means, scales)
        logit = trained.intercept + sum(w * f for w, f in zip(trained.weights, standardized))
        return _sigmoid(logit)

    def _infer_threshold(self, indication: str, feature_vector: FeatureVector) -> tuple[DecisionAction | None, float, str | None]:
        rules = self._threshold_rules.get(indication)
        if not rules:
            return None, 0.0, "no threshold rules registered for indication"
        name_to_value = dict(zip(feature_vector.feature_names, feature_vector.values))
        max_severity = 0.0
        selected: DecisionAction | None = "monitor"
        reasons: list[str] = []
        for metric, rule in rules.items():
            count = name_to_value.get(f"{metric}_count", 0.0)
            if count <= 0:
                continue
            latest = name_to_value.get(f"{metric}_latest", 0.0)
            review_threshold = rule.get("review_if_ge") or rule.get("review_if_le")
            escalate_threshold = rule.get("escalate_if_ge") or rule.get("escalate_if_le")
            if "review_if_ge" in rule and latest >= review_threshold:
                selected = "escalate"
                max_severity = max(max_severity, 0.9)
                reasons.append(f"{metric} latest {latest} >= review threshold {review_threshold}")
            elif "review_if_le" in rule and latest <= review_threshold:
                selected = "escalate"
                max_severity = max(max_severity, 0.9)
                reasons.append(f"{metric} latest {latest} <= review threshold {review_threshold}")
            elif "escalate_if_ge" in rule and latest >= escalate_threshold:
                selected = "escalate"
                max_severity = max(max_severity, 1.0)
                reasons.append(f"{metric} latest {latest} >= escalate threshold {escalate_threshold}")
            elif "escalate_if_le" in rule and latest <= escalate_threshold:
                selected = "escalate"
                max_severity = max(max_severity, 1.0)
                reasons.append(f"{metric} latest {latest} <= escalate threshold {escalate_threshold}")
            elif review_threshold is not None:
                selected = "review_required"
                max_severity = max(max_severity, 0.6)
                reasons.append(f"{metric} present but below review threshold")
        if selected is None or selected == "monitor":
            return None, 0.0, "no metric crossed a review threshold"
        return selected, round(max_severity, 4), "; ".join(reasons)

    def predict(
        self,
        model_id: str,
        indication: str,
        feature_vector: FeatureVector,
    ) -> tuple[DecisionAction | None, float, str | None, str]:
        """Run fast inference. Returns (action, confidence, reason, model_path)."""
        from .ml_governance import GovernanceError

        try:
            model_entry = self._lifecycle.get(model_id)
        except GovernanceError as exc:
            raise ModelInferenceError(str(exc)) from exc
        model_status = model_entry.get("status", "EXPERIMENTAL")
        if model_status not in STATUSES:
            raise ModelInferenceError("registered model has invalid lifecycle status")

        trained = self._load_trained(model_id)
        feature_names = list(feature_vector.feature_names)
        values = list(feature_vector.values)

        if trained is not None and trained.feature_names:
            trained_features = list(trained.feature_names)
            if set(trained_features) <= set(feature_names):
                aligned = [values[feature_names.index(name)] for name in trained_features]
                probability = self._infer_logistic(trained, aligned)
                action: DecisionAction | None = "escalate" if probability >= trained.decision_threshold else "review_required"
                reason = f"logistic regression probability {probability:.4f} >= threshold {trained.decision_threshold}"
                return action, round(probability, 4), reason, "logistic_regression"

        action, confidence, reason = self._infer_threshold(indication, feature_vector)
        return action, confidence, reason, "threshold_rules"
