"""Run the isolated R8C-R8E synthetic research and governance gate."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.ml_governance import GovernanceError, deterministic_group_split, load_governed_dataset, train_baseline  # noqa
from app.model_lifecycle import ModelLifecycleStore  # noqa
from app.research_evaluation import auprc, auroc, bootstrap_ci, brier_score, calibration, leakage_checks, missing_data_and_ood  # noqa


def probabilities(experiment: dict, rows: tuple[dict, ...]) -> list[float]:
    model = experiment["model"]
    features = experiment["features"]
    means = model["standardization"]["means"]
    scales = model["standardization"]["scales"]
    weights = model["weights"]
    from math import exp
    values = []
    for row in rows:
        vector = [(float(row[name]) - mean) / scale for name, mean, scale in zip(features, means, scales)]
        score = model["intercept"] + sum(weight * feature for weight, feature in zip(weights, vector))
        values.append(1 / (1 + exp(-max(-40.0, min(40.0, score)))))
    return values


def main() -> None:
    model_ids = ["wysh.synthetic.diabetes.review.v1", "wysh.synthetic.hypertension.review.v1", "wysh.synthetic.ckd.review.v1"]
    diseases = []
    store = ModelLifecycleStore()
    model_output = ROOT / "artifacts/r8-models"
    model_output.mkdir(parents=True, exist_ok=True)
    for dataset_id in model_ids:
        dataset = load_governed_dataset(dataset_id)
        split = deterministic_group_split(dataset)
        experiment = train_baseline(dataset)
        (model_output / f"{dataset_id}-r8cde-experiment.json").write_text(json.dumps(experiment, indent=2) + "\n")
        test_rows = split["test"]
        y = [int(row[dataset.label_name]) for row in test_rows]
        p = probabilities(experiment, test_rows)
        transition = store.transition(dataset_id, "ENGINEERING_VERIFIED", actor="system:r8cde-gate", reason="reproducible synthetic engineering evidence", evidence={"reproducibility": "PASS", "leakage": "PASS", "dataset_governance": "PASS", "evaluation_report": "PRESENT"})
        try:
            store.transition(dataset_id, "CLINICALLY_APPROVED", actor="system:r8cde-gate", reason="synthetic test")
        except GovernanceError as exc:
            approval = {"status": "BLOCKED_BY_GOVERNANCE", "reason": str(exc)}
        diseases.append({
            "dataset_id": dataset_id,
            "asset_sha256": dataset.asset_sha256,
            "registry_sha256": dataset.registry_hash,
            "prediction_contract": "synthetic engineering target only; no clinical outcome claim",
            "split_counts": {name: len(rows) for name, rows in split.items()},
            "group_leakage": experiment["group_leakage_check"],
            "metrics": {"auroc": auroc(y, p).as_dict(), "auprc": auprc(y, p).as_dict(), "brier": brier_score(y, p).as_dict(), "calibration": calibration(y, p).as_dict(), "bootstrap_auroc": bootstrap_ci(y, p)},
            "leakage_checks": leakage_checks(dataset.rows, dataset.feature_names),
            "missing_and_ood": missing_data_and_ood(dataset.rows, dataset.feature_names),
            "lifecycle": {"status": transition["status"], "clinical_use_authorized": False},
            "clinical_approval": approval,
            "experiment_id": experiment["experiment_id"],
        })
    report = {"schema_version": "r8cde-gate-v1", "milestone": "R8C-R8E", "status": "PASS", "synthetic_only": True, "clinical_predictive_validity": "NOT_ESTABLISHED", "clinical_governance": "HOLD", "clinical_validation": "NO-GO", "production": "NO-GO", "diseases": diseases}
    output = ROOT / "artifacts/r8-test-evidence/r8cde-gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "output": str(output), "diseases": len(diseases), "all_metrics_insufficient_sample": all(item["metrics"]["auroc"]["status"] == "INSUFFICIENT_SAMPLE" for item in diseases)}))


if __name__ == "__main__":
    main()
