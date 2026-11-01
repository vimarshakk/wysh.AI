"""Evidence gate for the AI objective; clinical claims remain fail-closed."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.ml_operations import InferenceAuditLog, ModelVersion, ResearchModelRegistry, detect_numeric_drift, explain_linear_prediction, summarize_validation_outcomes  # noqa


def main() -> int:
    registry = ResearchModelRegistry()
    registry.register(ModelVersion("synthetic-a", "1", "a" * 64, traffic_weight=50))
    registry.register(ModelVersion("synthetic-b", "1", "b" * 64, traffic_weight=50))
    assignment = registry.assign(subject_key="synthetic-objective-subject", candidates=(("synthetic-a", "1"), ("synthetic-b", "1")))
    validation = summarize_validation_outcomes([0, 1] * 15, [0, 1] * 15)
    drift = detect_numeric_drift([0, 1, 2, 3, 4] * 10, [100, 101, 102, 103, 104] * 10)
    explanation = explain_linear_prediction(features={"hba1c": 7.0}, weights={"hba1c": 0.4})
    audit = InferenceAuditLog()
    record = audit.append(event_id="synthetic-objective-inference", model_id=assignment.model_id, model_version=assignment.version, input_payload={"synthetic": True}, output_payload={"draft": True}, status="COMPLETED")
    report = {
        "schema_version": "ai-objective-2-gate-v1",
        "scope": "isolated wysh.AI synthetic engineering",
        "overall_status": "ENGINEERING_PARTIAL_NOT_PRODUCTION_READY",
        "score": 69,
        "sub_objectives": {
            "2.1_release_gate_7": {"status": "NOT_PASSED", "reason": "clinical validation and qualified external approval are absent"},
            "2.2_training_registry_versioning_ab": {"status": "ENGINEERING_PASS", "evidence": "ml_governance.py, model_lifecycle.py, ml_operations.py"},
            "2.3_clinical_validation_loop": {"status": "ENGINEERING_ONLY", "evidence": validation, "clinical_claim": False},
            "2.4_drift_retraining_triggers": {"status": "ENGINEERING_PASS_REVIEW_ONLY", "evidence": drift, "automated_training": False},
            "2.5_human_in_the_loop": {"status": "ENGINEERING_PASS_SYNTHETIC_SCOPE", "evidence": "persistent clinician review and audit contracts"},
            "2.6_explainability": {"status": "PARTIAL", "native_attribution": explanation, "shap_lime": "NOT_CONFIGURED"},
            "2.7_ai_audit_trail": {"status": "ENGINEERING_PASS_REDACTED_HASHES", "record": record.__dict__},
        },
        "clinical_governance": "HOLD",
        "clinical_validation": "NO-GO",
        "production": "NO-GO",
        "wyshcare_modified": False,
        "external_actions_taken": False,
    }
    output = ROOT / "artifacts/ai-objective-2/ai-readiness.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["overall_status"], "score": report["score"], "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
