"""Deterministic feature extraction for the System One decision model.

Typed clinical facts are converted into a bounded numeric feature vector.
No free text, no raw documents, no PHI identifiers are accepted. Extraction is
fully deterministic: the same input always produces the same feature vector.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Literal

from pydantic import BaseModel, Field


class ClinicalFact(BaseModel):
    source_id: str = Field(min_length=1, max_length=200)
    source_type: Literal["observation", "condition", "medication", "encounter"]
    recorded_at: str = Field(min_length=1, max_length=100)
    metric: str | None = Field(default=None, max_length=100)
    value: float | None = Field(default=None)
    unit: str | None = Field(default=None, max_length=50)
    code: str | None = Field(default=None, max_length=100)
    status: Literal["active", "resolved", "inactive", "unknown"] | None = Field(default=None)
    severity: Literal["mild", "moderate", "severe", "critical", "unknown"] | None = Field(default=None)


class FeatureVector(BaseModel):
    feature_names: tuple[str, ...]
    values: tuple[float, ...]
    missing_flags: tuple[str, ...]
    input_hash: str


class FeatureExtractorError(ValueError):
    pass


_NUMERIC_METRICS = frozenset({"hba1c_percent", "mean_glucose_mg_dl", "bp_systolic_mmhg", "bp_diastolic_mmhg", "egfr_ml_min_1_73m2", "urine_acr_mg_g", "age_years"})
_BINARY_FLAGS = frozenset({"hypertension", "diabetes", "chronic_kidney_disease", "smoking", "pregnancy"})


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _metric_key(fact: ClinicalFact) -> str | None:
    if fact.metric and fact.metric in _NUMERIC_METRICS:
        return fact.metric
    return None


def _flag_key(fact: ClinicalFact) -> str | None:
    if fact.source_type == "condition" and fact.code and fact.code in _BINARY_FLAGS:
        return fact.code
    return None


def extract(facts: list[ClinicalFact]) -> FeatureVector:
    if len(facts) > 500:
        raise FeatureExtractorError("fact count exceeds the bounded input limit")
    for fact in facts:
        if fact.value is not None and not (0.0 <= fact.value <= 1e6):
            raise FeatureExtractorError(f"fact value out of bounded range: {fact.source_id}")

    observations: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
    flags: dict[str, bool] = {}
    evidence_refs: list[str] = []

    for fact in facts:
        evidence_refs.append(fact.source_id)
        key = _metric_key(fact)
        if key is not None and fact.value is not None:
            try:
                recorded_at = _parse_iso(fact.recorded_at)
            except ValueError as exc:
                raise FeatureExtractorError(f"invalid recorded_at for {fact.source_id}") from exc
            observations[key].append((recorded_at, fact.value))
        flag_key = _flag_key(fact)
        if flag_key is not None:
            flags[flag_key] = True

    all_metrics = sorted(_NUMERIC_METRICS)
    missing = [metric for metric in all_metrics if metric not in observations]
    feature_names: list[str] = []
    values: list[float] = []

    now = _now()
    for metric in all_metrics:
        series = observations.get(metric, [])
        feature_names.append(f"{metric}_count")
        values.append(float(len(series)))
        feature_names.append(f"{metric}_mean")
        feature_names.append(f"{metric}_min")
        feature_names.append(f"{metric}_max")
        feature_names.append(f"{metric}_latest")
        feature_names.append(f"{metric}_stale_days")

        if series:
            sorted_series = sorted(series, key=lambda item: item[0])
            values_of_metric = [value for _, value in sorted_series]
            mean = sum(values_of_metric) / len(values_of_metric)
            latest_time, latest_value = sorted_series[-1]
            stale_days = max(0, (now - latest_time).days)
            values.extend([mean, min(values_of_metric), max(values_of_metric), latest_value, float(stale_days)])
        else:
            values.extend([0.0, 0.0, 0.0, 0.0, float(len(all_metrics) * 365)])

    for flag in sorted(_BINARY_FLAGS):
        feature_names.append(f"flag_{flag}")
        values.append(1.0 if flags.get(flag) is True else 0.0)

    feature_names.append("total_evidence_count")
    values.append(float(len(evidence_refs)))

    canonical = {
        "facts": [fact.model_dump(mode="json") for fact in facts],
    }
    input_hash = sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    return FeatureVector(
        feature_names=tuple(feature_names),
        values=tuple(values),
        missing_flags=tuple(missing),
        input_hash=input_hash,
    )


def required_metrics_for(indication: str) -> tuple[str, ...]:
    requirements = {
        "diabetes": ("hba1c_percent", "mean_glucose_mg_dl", "age_years"),
        "hypertension": ("bp_systolic_mmhg", "bp_diastolic_mmhg", "age_years"),
        "chronic_kidney_disease": ("egfr_ml_min_1_73m2", "urine_acr_mg_g", "age_years"),
    }
    return requirements.get(indication, ())
