"""R8A/R8B dataset governance and dependency-free baseline training.

This module is intentionally small and auditable. It supports only original
synthetic JSONL assets registered in the repository. It does not ingest PHI,
download datasets, or make clinical predictions.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import exp
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parents[3]
REGISTRY_PATH = ROOT / "research/datasets/registry-v1.json"
FEATURES = ("hba1c_percent", "mean_glucose_mg_dl", "age_years")
LABEL = "synthetic_review_required"


class GovernanceError(ValueError):
    pass


@dataclass(frozen=True)
class GovernedDataset:
    dataset_id: str
    version: str
    asset_path: Path
    asset_sha256: str
    rows: tuple[dict[str, Any], ...]
    registry_hash: str
    split_policy: dict[str, Any]
    feature_names: tuple[str, ...]
    label_name: str


def digest_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def canonical_hash(value: Any) -> str:
    return digest_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _read_registry() -> tuple[dict[str, Any], str]:
    raw = REGISTRY_PATH.read_bytes()
    try:
        registry = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GovernanceError("dataset registry is not valid JSON") from exc
    if registry.get("schema_version") != "r8a-dataset-registry-v1" or registry.get("synthetic_only") is not True:
        raise GovernanceError("dataset registry schema or synthetic-only flag is invalid")
    return registry, digest_bytes(raw)


def load_governed_dataset(dataset_id: str, version: str = "1.0.0") -> GovernedDataset:
    registry, registry_hash = _read_registry()
    entries = [item for item in registry.get("datasets", []) if item.get("dataset_id") == dataset_id and item.get("version") == version]
    if len(entries) != 1:
        raise GovernanceError("dataset is not uniquely registered")
    entry = entries[0]
    if entry.get("source_type") != "original_synthetic" or entry.get("synthetic_only") is not True or entry.get("contains_phi") is not False:
        raise GovernanceError("only original synthetic non-PHI datasets are permitted")
    if not entry.get("rights_owner") or not entry.get("license") or not entry.get("license_evidence"):
        raise GovernanceError("dataset rights and license evidence are required")
    asset_path = (ROOT / entry["asset_path"]).resolve()
    if ROOT not in asset_path.parents or not asset_path.is_file():
        raise GovernanceError("registered dataset asset is missing or outside the repository")
    asset_bytes = asset_path.read_bytes()
    feature_names = tuple(name for name in entry.get("feature_schema", {}).keys() if name not in {"patient_id", "observed_at"})
    label_name = next(iter(entry.get("label_schema", {}).keys()), "")
    if not feature_names or not label_name:
        raise GovernanceError("feature and label schemas are required")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(asset_bytes.decode("utf-8").splitlines(), start=1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise GovernanceError(f"dataset row {line_number} is not valid JSON") from exc
        if row.get("patient_id", "").startswith("synthetic-") is not True or row.get(label_name) not in {0, 1}:
            raise GovernanceError(f"dataset row {line_number} is not synthetic and schema-valid")
        if any(not isinstance(row.get(feature), (int, float)) for feature in feature_names):
            raise GovernanceError(f"dataset row {line_number} has invalid feature types")
        rows.append(row)
    if not rows:
        raise GovernanceError("dataset cannot be empty")
    return GovernedDataset(dataset_id, version, asset_path, digest_bytes(asset_bytes), tuple(rows), registry_hash, entry["split_policy"], feature_names, label_name)


def deterministic_group_split(dataset: GovernedDataset) -> dict[str, tuple[dict[str, Any], ...]]:
    rows = sorted(dataset.rows, key=lambda row: row["patient_id"])
    groups = [row["patient_id"] for row in rows]
    if len(groups) != len(set(groups)):
        raise GovernanceError("patient groups must be unique in this baseline dataset")
    ratios = dataset.split_policy.get("ratios", {})
    train_end = int(len(rows) * ratios.get("train", 0.6))
    validation_end = train_end + int(len(rows) * ratios.get("validation", 0.2))
    if train_end <= 0 or validation_end >= len(rows):
        raise GovernanceError("split policy produced an empty partition")
    split = {"train": tuple(rows[:train_end]), "validation": tuple(rows[train_end:validation_end]), "test": tuple(rows[validation_end:])}
    seen: dict[str, str] = {}
    for name, partition in split.items():
        for row in partition:
            group = row["patient_id"]
            if group in seen:
                raise GovernanceError(f"group leakage detected for {group}")
            seen[group] = name
    return split


def _standardize(train: tuple[dict[str, Any], ...], rows: tuple[dict[str, Any], ...], feature_names: tuple[str, ...]) -> tuple[list[list[float]], dict[str, list[float]]]:
    means = [sum(float(row[name]) for row in train) / len(train) for name in feature_names]
    scales = [max((sum((float(row[name]) - mean) ** 2 for row in train) / len(train)) ** 0.5, 1e-9) for name, mean in zip(feature_names, means)]
    matrix = [[(float(row[name]) - mean) / scale for name, mean, scale in zip(feature_names, means, scales)] for row in rows]
    return matrix, {"means": means, "scales": scales}


def _sigmoid(value: float) -> float:
    value = max(-40.0, min(40.0, value))
    return 1.0 / (1.0 + exp(-value))


def _metrics(rows: tuple[dict[str, Any], ...], probabilities: list[float], label_name: str) -> dict[str, float | int]:
    labels = [int(row[label_name]) for row in rows]
    predictions = [1 if probability >= 0.5 else 0 for probability in probabilities]
    correct = sum(prediction == label for prediction, label in zip(predictions, labels))
    brier = sum((probability - label) ** 2 for probability, label in zip(probabilities, labels)) / len(labels)
    positives = sum(labels)
    negatives = len(labels) - positives
    tp = sum(prediction == label == 1 for prediction, label in zip(predictions, labels))
    tn = sum(prediction == label == 0 for prediction, label in zip(predictions, labels))
    return {"count": len(labels), "accuracy": round(correct / len(labels), 6), "brier": round(brier, 6), "positive_count": positives, "negative_count": negatives, "sensitivity": round(tp / positives, 6) if positives else 0.0, "specificity": round(tn / negatives, 6) if negatives else 0.0}


def train_baseline(dataset: GovernedDataset, *, seed: int = 20261024, epochs: int = 300, learning_rate: float = 0.08) -> dict[str, Any]:
    feature_names, label_name = dataset.feature_names, dataset.label_name
    split = deterministic_group_split(dataset)
    train_rows = split["train"]
    train_matrix, standardization = _standardize(train_rows, train_rows, feature_names)
    weights = [0.0] * (len(feature_names) + 1)
    for _ in range(epochs):
        gradients = [0.0] * len(weights)
        for row, features in zip(train_rows, train_matrix):
            probability = _sigmoid(weights[0] + sum(weight * feature for weight, feature in zip(weights[1:], features)))
            error = probability - int(row[label_name])
            gradients[0] += error
            for index, feature in enumerate(features, start=1):
                gradients[index] += error * feature
        for index in range(len(weights)):
            weights[index] -= learning_rate * gradients[index] / len(train_rows)
    metrics: dict[str, Any] = {}
    for name, rows in split.items():
        matrix, _ = _standardize(train_rows, rows, feature_names)
        probabilities = [_sigmoid(weights[0] + sum(weight * feature for weight, feature in zip(weights[1:], features))) for features in matrix]
        metrics[name] = _metrics(rows, probabilities, label_name)
    experiment = {
        "experiment_id": f"r8b-{dataset.dataset_id}-{dataset.version}-seed-{seed}",
        "schema_version": "r8b-experiment-v1",
        "seed": seed,
        "algorithm": "dependency-free-logistic-regression",
        "features": list(feature_names),
        "label": label_name,
        "hyperparameters": {"epochs": epochs, "learning_rate": learning_rate},
        "dataset": {"dataset_id": dataset.dataset_id, "version": dataset.version, "asset_sha256": dataset.asset_sha256, "registry_sha256": dataset.registry_hash, "split_policy": dataset.split_policy},
        "split_counts": {name: len(rows) for name, rows in split.items()},
        "group_leakage_check": "PASS",
        "metrics": metrics,
        "model": {"intercept": round(weights[0], 12), "weights": [round(weight, 12) for weight in weights[1:]], "standardization": standardization},
        "clinical_use_authorized": False,
        "synthetic_only": True,
        "provenance_hash": canonical_hash({"dataset": dataset.asset_sha256, "registry": dataset.registry_hash, "config": {"seed": seed, "epochs": epochs, "learning_rate": learning_rate}, "model": weights}),
    }
    return experiment


def train_interpretable_comparator(dataset: GovernedDataset, *, seed: int = 20261024) -> dict[str, Any]:
    """Prevalence-only comparator; useful as a transparent research baseline."""
    split = deterministic_group_split(dataset)
    train_rows = split["train"]
    prevalence = sum(int(row[dataset.label_name]) for row in train_rows) / len(train_rows)
    metrics: dict[str, Any] = {}
    for name, rows in split.items():
        metrics[name] = _metrics(rows, [prevalence] * len(rows), dataset.label_name)
    return {
        "experiment_id": f"r13-comparator-{dataset.dataset_id}-{dataset.version}-seed-{seed}",
        "schema_version": "r13-comparator-v1",
        "seed": seed,
        "algorithm": "constant-prevalence-interpretable-comparator",
        "features": [],
        "label": dataset.label_name,
        "dataset": {"dataset_id": dataset.dataset_id, "version": dataset.version, "asset_sha256": dataset.asset_sha256, "registry_sha256": dataset.registry_hash, "split_policy": dataset.split_policy},
        "train_prevalence": round(prevalence, 12),
        "split_counts": {name: len(rows) for name, rows in split.items()},
        "group_leakage_check": "PASS",
        "metrics": metrics,
        "clinical_use_authorized": False,
        "synthetic_only": True,
        "provenance_hash": canonical_hash({"dataset": dataset.asset_sha256, "registry": dataset.registry_hash, "config": {"seed": seed}, "prevalence": prevalence}),
    }
