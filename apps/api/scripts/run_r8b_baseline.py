"""Run the reproducible synthetic R8B baseline experiment."""

from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml_governance import load_governed_dataset, train_baseline  # noqa: E402


def main() -> int:
    dataset = load_governed_dataset("wysh.synthetic.diabetes.review.v1")
    experiment = train_baseline(dataset)
    output = Path(__file__).parents[3] / "artifacts" / "r8-test-evidence" / "r8b-experiment.json"
    model_output = Path(__file__).parents[3] / "artifacts" / "r8-models" / f"{experiment['experiment_id']}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    model_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(experiment, indent=2) + "\n", encoding="utf-8")
    model_output.write_text(json.dumps({"schema_version": "r8b-model-artifact-v1", "experiment_id": experiment["experiment_id"], "model": experiment["model"], "provenance_hash": experiment["provenance_hash"], "synthetic_only": True, "clinical_use_authorized": False}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "evidence_file": str(output), "model_artifact": str(model_output), "experiment_id": experiment["experiment_id"], "metrics": experiment["metrics"], "group_leakage_check": experiment["group_leakage_check"], "clinical_use_authorized": experiment["clinical_use_authorized"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
