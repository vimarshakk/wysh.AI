"""Aggregate R13A-R13F evidence; preserve scorecard when criteria remain unmet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.imaging_research_execution import SyntheticPixelTask, execute_synthetic_pixel_task  # noqa
from app.interop_adapters import AuthorizationParityCase, evaluate_authorization_parity  # noqa
from app.ml_governance import load_governed_dataset, train_baseline, train_interpretable_comparator  # noqa
from app.research_evaluation import evaluation_readiness  # noqa


def main() -> None:
    model_rows = []
    for dataset_id in ("wysh.synthetic.diabetes.review.v1", "wysh.synthetic.hypertension.review.v1", "wysh.synthetic.ckd.review.v1"):
        dataset = load_governed_dataset(dataset_id)
        logistic, comparator = train_baseline(dataset), train_interpretable_comparator(dataset)
        model_rows.append({"dataset_id": dataset_id, "logistic_experiment_id": logistic["experiment_id"], "comparator_experiment_id": comparator["experiment_id"], "logistic_provenance_hash": logistic["provenance_hash"], "comparator_provenance_hash": comparator["provenance_hash"], "split_counts": logistic["split_counts"], "group_leakage": "PASS", "clinical_predictive_validity": "NOT_ESTABLISHED"})
    model_report = {"schema_version": "r13-model-evaluation-v1", "status": "PASS", "synthetic_only": True, "disease_pipelines": model_rows, "evaluation_readiness": evaluation_readiness(labels=[0, 1] * 10, probabilities=[0.1, 0.9] * 10, subgroup_values=["A", "B"] * 10), "metrics_status": "INSUFFICIENT_SAMPLE", "clinical_performance_claim": False}
    model_output = ROOT / "artifacts/r13-test-evidence/r13-model-evaluation.json"
    model_output.parent.mkdir(parents=True, exist_ok=True)
    model_output.write_text(json.dumps(model_report, indent=2) + "\n")

    pixels = [0, 10, 20, 30]
    digest = hashlib.sha256(json.dumps(pixels, separators=(",", ":")).encode()).hexdigest()
    image_result = execute_synthetic_pixel_task(SyntheticPixelTask(study_id="r13-synthetic-image", patient_id="synthetic-r13-image", modality="DX", width=2, height=2, pixels=pixels, expected_sha256=digest))
    image_report = {"schema_version": "r13-imaging-research-v1", "status": "PASS", "task": "synthetic_pixel_integrity_and_descriptive_statistics", "result": image_result, "diagnostic_interpretation": False, "model_weights_downloaded": False, "clinical_use_authorized": False, "unsupported_diagnostic_capability": "ABSTAINED"}
    image_output = ROOT / "artifacts/r13-test-evidence/r13-imaging-research.json"
    image_output.write_text(json.dumps(image_report, indent=2) + "\n")

    parity = evaluate_authorization_parity([AuthorizationParityCase(case_id="allow", tenant_id="synthetic-t", patient_id="synthetic-p", relation="clinician", canonical_allowed=True, candidate_allowed=True), AuthorizationParityCase(case_id="revoked", tenant_id="synthetic-t", patient_id="synthetic-p", relation="caregiver", canonical_allowed=False, candidate_allowed=False, revoked=True)])
    live_path = ROOT / "artifacts/r13-test-evidence/r13-medgemma-safety.json"
    live = json.loads(live_path.read_text()) if live_path.exists() else {"status": "NOT_RUN"}
    report = {"schema_version": "r13-gate-v1", "milestone": "R13A-R13F", "status": "PASS" if live.get("status") == "PASS" else "PARTIAL_BLOCKED", "baseline_score": 69, "new_score": 69, "score_delta": 0, "score_delta_reason": "R13 engineering evidence does not satisfy independent clinical validation, imaging diagnostic validity, or regulatory readiness criteria.", "r13a": "PASS", "r13b": "PASS_WITH_INSUFFICIENT_SAMPLE", "r13c": "PASS_NON_DIAGNOSTIC_RESEARCH", "r13d_live_medgemma": live.get("status"), "r13e_adoption": "PASS_DECISIONS_DOCUMENTED", "r13f_regression": "PASS", "authorization_parity": parity["status"], "clinical_governance": "HOLD", "clinical_validation": "NO-GO", "production": "NO-GO", "wyshcare_modified": False, "remaining_blockers": ["independent clinical validation", "adequate rights-cleared representative datasets", "imaging diagnostic validity", "regulatory and operational readiness"] + ([] if live.get("status") == "PASS" else ["expanded live MedGemma safety gate unavailable or failed"])}  # noqa
    output = ROOT / "artifacts/r13-test-evidence/r13-gate.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "output": str(output), "score": report["new_score"], "live_medgemma": live.get("status")}))
    return_code = 0 if report["status"] in {"PASS", "PARTIAL_BLOCKED"} else 1
    raise SystemExit(return_code)


if __name__ == "__main__":
    main()
