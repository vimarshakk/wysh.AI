"""Fail-closed, dependency-free evaluation contracts for synthetic research runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isnan
from random import Random
from typing import Any, Iterable


INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"


@dataclass(frozen=True)
class EvaluationResult:
    status: str
    metric: str
    value: float | None = None
    reason: str | None = None
    sample_size: int = 0
    positive_count: int = 0
    negative_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {key: value for key, value in self.__dict__.items() if value is not None}


def _counts(labels: list[int]) -> tuple[int, int]:
    return sum(labels), len(labels) - sum(labels)


def _insufficient(metric: str, labels: list[int], reason: str) -> EvaluationResult:
    positives, negatives = _counts(labels)
    return EvaluationResult(INSUFFICIENT_SAMPLE, metric, reason=reason, sample_size=len(labels), positive_count=positives, negative_count=negatives)


def _ready(metric: str, labels: list[int], minimum_n: int) -> EvaluationResult | None:
    positives, negatives = _counts(labels)
    if len(labels) < minimum_n:
        return _insufficient(metric, labels, f"requires at least {minimum_n} observations")
    if not positives or not negatives:
        return _insufficient(metric, labels, "requires both positive and negative classes")
    return None


def brier_score(labels: Iterable[int], probabilities: Iterable[float]) -> EvaluationResult:
    ys, ps = list(labels), list(probabilities)
    if len(ys) != len(ps) or not ys:
        return EvaluationResult(INSUFFICIENT_SAMPLE, "brier", reason="labels and probabilities must be non-empty and aligned", sample_size=len(ys))
    bad = _ready("brier", ys, 30)
    if bad:
        return bad
    return EvaluationResult("PASS", "brier", sum((float(p) - y) ** 2 for y, p in zip(ys, ps)) / len(ys), sample_size=len(ys), positive_count=sum(ys), negative_count=len(ys) - sum(ys))


def classification_metrics(labels: Iterable[int], probabilities: Iterable[float], *, threshold: float = 0.5, minimum_n: int = 30) -> dict[str, Any]:
    ys, ps = list(labels), list(probabilities)
    if len(ys) != len(ps) or not ys or any(y not in {0, 1} for y in ys) or any(not isinstance(p, (int, float)) or not 0 <= float(p) <= 1 for p in ps):
        return {"status": "INVALID_DATA", "metric": "classification_metrics", "reason": "aligned binary labels and finite probabilities in [0,1] are required"}
    if not any(ys) or all(ys):
        return {"status": INSUFFICIENT_SAMPLE, "metric": "classification_metrics", "reason": "both positive and negative classes are required", "sample_size": len(ys)}
    if len(ys) < minimum_n:
        return {"status": INSUFFICIENT_SAMPLE, "metric": "classification_metrics", "reason": f"requires at least {minimum_n} observations", "sample_size": len(ys)}
    predicted = [int(p >= threshold) for p in ps]
    tp = sum(y == 1 and p == 1 for y, p in zip(ys, predicted)); tn = sum(y == 0 and p == 0 for y, p in zip(ys, predicted)); fp = sum(y == 0 and p == 1 for y, p in zip(ys, predicted)); fn = sum(y == 1 and p == 0 for y, p in zip(ys, predicted))
    return {"status": "VALID", "sensitivity": tp / (tp + fn) if tp + fn else None, "specificity": tn / (tn + fp) if tn + fp else None, "ppv": tp / (tp + fp) if tp + fp else None, "npv": tn / (tn + fn) if tn + fn else None, "sample_size": len(ys), "positive_count": sum(ys), "negative_count": len(ys) - sum(ys)}


def calibration_parameters(labels: Iterable[int], probabilities: Iterable[float], *, minimum_n: int = 30) -> dict[str, Any]:
    ys, ps = list(labels), list(probabilities)
    if len(ys) != len(ps) or not ys or any(y not in {0, 1} for y in ys) or any(not isinstance(p, (int, float)) or not 0 < float(p) < 1 for p in ps):
        return {"status": "INVALID_DATA", "metric": "calibration_parameters", "reason": "aligned binary labels and probabilities strictly inside (0,1) are required"}
    if len(ys) < minimum_n or not any(ys) or all(ys):
        return {"status": INSUFFICIENT_SAMPLE, "metric": "calibration_parameters", "reason": "adequate sample and both classes are required", "sample_size": len(ys)}
    return {"status": INSUFFICIENT_SAMPLE, "metric": "calibration_parameters", "reason": "calibration fit requires a separately governed regression implementation", "sample_size": len(ys)}


def auroc(labels: Iterable[int], probabilities: Iterable[float]) -> EvaluationResult:
    ys, ps = list(labels), list(probabilities)
    bad = _ready("auroc", ys, 30) if len(ys) == len(ps) else _insufficient("auroc", ys, "labels and probabilities must be aligned")
    if bad:
        return bad
    positives = [p for y, p in zip(ys, ps) if y == 1]
    negatives = [p for y, p in zip(ys, ps) if y == 0]
    wins = sum(1 if p > n else 0.5 if p == n else 0 for p in positives for n in negatives)
    return EvaluationResult("PASS", "auroc", wins / (len(positives) * len(negatives)), sample_size=len(ys), positive_count=len(positives), negative_count=len(negatives))


def auprc(labels: Iterable[int], probabilities: Iterable[float]) -> EvaluationResult:
    ys, ps = list(labels), list(probabilities)
    bad = _ready("auprc", ys, 30) if len(ys) == len(ps) else _insufficient("auprc", ys, "labels and probabilities must be aligned")
    if bad:
        return bad
    positives = sum(ys)
    order = sorted(range(len(ys)), key=lambda i: ps[i], reverse=True)
    tp = 0
    area = 0.0
    previous_recall = 0.0
    for rank, index in enumerate(order, start=1):
        if ys[index]:
            tp += 1
            recall = tp / positives
            area += (recall - previous_recall) * (tp / rank)
            previous_recall = recall
    return EvaluationResult("PASS", "auprc", area, sample_size=len(ys), positive_count=positives, negative_count=len(ys) - positives)


def calibration(labels: Iterable[int], probabilities: Iterable[float], bins: int = 5) -> EvaluationResult:
    ys, ps = list(labels), list(probabilities)
    bad = _ready("calibration", ys, 30) if len(ys) == len(ps) else _insufficient("calibration", ys, "labels and probabilities must be aligned")
    if bad:
        return bad
    error = 0.0
    for bucket in range(bins):
        selected = [(y, p) for y, p in zip(ys, ps) if bucket / bins <= p < (bucket + 1) / bins or bucket == bins - 1 and p == 1]
        if selected:
            error += abs(sum(y for y, _ in selected) / len(selected) - sum(p for _, p in selected) / len(selected)) * len(selected) / len(ys)
    return EvaluationResult("PASS", "expected_calibration_error", error, sample_size=len(ys), positive_count=sum(ys), negative_count=len(ys) - sum(ys))


def bootstrap_ci(labels: Iterable[int], probabilities: Iterable[float], metric: str = "auroc", *, seed: int = 20261024, replicates: int = 200) -> dict[str, Any]:
    ys, ps = list(labels), list(probabilities)
    if len(ys) < 30 or sum(ys) < 5 or len(ys) - sum(ys) < 5:
        return {"status": INSUFFICIENT_SAMPLE, "metric": f"{metric}_bootstrap_ci", "reason": "requires n>=30 and at least five observations in each class", "sample_size": len(ys)}
    scorer = auroc if metric == "auroc" else auprc
    rng = Random(seed)
    values: list[float] = []
    for _ in range(replicates):
        indices = [rng.randrange(len(ys)) for _ in ys]
        result = scorer([ys[i] for i in indices], [ps[i] for i in indices])
        if result.status == "PASS" and result.value is not None:
            values.append(result.value)
    if len(values) < 20:
        return {"status": INSUFFICIENT_SAMPLE, "metric": f"{metric}_bootstrap_ci", "reason": "bootstrap replicates lacked both classes", "sample_size": len(ys)}
    values.sort()
    return {"status": "PASS", "metric": f"{metric}_bootstrap_ci", "lower": values[int(len(values) * 0.025)], "upper": values[int(len(values) * 0.975) - 1], "replicates": len(values)}


def subgroup_evaluation(rows: Iterable[dict[str, Any]], labels: Iterable[int], probabilities: Iterable[float], subgroup_key: str, *, minimum_n: int = 10) -> dict[str, Any]:
    rows, ys, ps = list(rows), list(labels), list(probabilities)
    groups: dict[str, list[int]] = {}
    for index, row in enumerate(rows):
        groups.setdefault(str(row.get(subgroup_key, "MISSING")), []).append(index)
    return {group: ({"status": INSUFFICIENT_SAMPLE, "reason": f"requires at least {minimum_n} observations", "sample_size": len(indices)} if len(indices) < minimum_n else auroc([ys[i] for i in indices], [ps[i] for i in indices]).as_dict()) for group, indices in groups.items()}


def leakage_checks(rows: Iterable[dict[str, Any]], feature_names: Iterable[str], *, index_date_key: str = "observed_at", feature_cutoff_key: str = "feature_cutoff") -> dict[str, Any]:
    rows = list(rows)
    patient_ids = [row.get("patient_id") for row in rows]
    duplicate_groups = len(patient_ids) != len(set(patient_ids))
    future_features = []
    for row in rows:
        if row.get(feature_cutoff_key) and row.get(index_date_key) and str(row[feature_cutoff_key]) > str(row[index_date_key]):
            future_features.append(row.get("patient_id"))
    return {"patient_group_leakage": "FAIL" if duplicate_groups else "PASS", "temporal_feature_leakage": "FAIL" if future_features else "PASS", "future_feature_patients": future_features, "required_features": list(feature_names)}


def missing_data_and_ood(rows: Iterable[dict[str, Any]], feature_names: Iterable[str]) -> dict[str, Any]:
    rows = list(rows)
    missing = [row.get("patient_id") for row in rows if any(row.get(name) is None for name in feature_names)]
    ood = [row.get("patient_id") for row in rows if any(isinstance(row.get(name), (int, float)) and (isnan(float(row[name])) or float(row[name]) < 0) for name in feature_names)]
    return {"missing_data": {"status": "ABSTAIN" if missing else "PASS", "patient_ids": missing}, "out_of_distribution": {"status": "ABSTAIN" if ood else "PASS", "patient_ids": ood}}


def evaluation_readiness(*, labels: Iterable[int], probabilities: Iterable[float], subgroup_values: Iterable[str], minimum_n: int = 100, minimum_per_class: int = 20) -> dict[str, Any]:
    """Assess whether a cohort is ready for meaningful validation, without scoring it."""
    ys, ps, groups = list(labels), list(probabilities), list(subgroup_values)
    positives, negatives = _counts(ys)
    aligned = len(ys) == len(ps) == len(groups)
    sample_status = "READY" if aligned and len(ys) >= minimum_n and positives >= minimum_per_class and negatives >= minimum_per_class else INSUFFICIENT_SAMPLE
    subgroup_counts: dict[str, int] = {}
    for group in groups:
        subgroup_counts[str(group)] = subgroup_counts.get(str(group), 0) + 1
    subgroup_status = "READY" if subgroup_counts and min(subgroup_counts.values()) >= minimum_per_class else INSUFFICIENT_SAMPLE
    uncertainty = {"status": "READY" if ps else INSUFFICIENT_SAMPLE, "range": [min(ps), max(ps)] if ps else None, "mean_probability": sum(ps) / len(ps) if ps else None}
    return {"sample_adequacy": {"status": sample_status, "sample_size": len(ys), "positive_count": positives, "negative_count": negatives, "minimum_n": minimum_n, "minimum_per_class": minimum_per_class}, "alignment": "PASS" if aligned else "FAIL", "subgroup_adequacy": {"status": subgroup_status, "counts": subgroup_counts}, "uncertainty_contract": uncertainty, "external_validation_readiness": "READY_ONLY_AFTER_INDEPENDENT_DATASET_AND_RIGHTS_REVIEW"}
