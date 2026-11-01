from app.ml_operations import DriftMonitor, InferenceAuditLog, ModelVersion, ResearchModelRegistry, detect_numeric_drift, explain_linear_prediction, summarize_validation_outcomes


def test_registry_is_immutable_and_deterministic_for_ab_assignment():
    registry = ResearchModelRegistry()
    registry.register(ModelVersion("synthetic-a", "1", "a" * 64, traffic_weight=50))
    registry.register(ModelVersion("synthetic-b", "1", "b" * 64, traffic_weight=50))
    first = registry.assign(subject_key="synthetic-subject-1", candidates=(("synthetic-a", "1"), ("synthetic-b", "1")))
    second = registry.assign(subject_key="synthetic-subject-1", candidates=(("synthetic-a", "1"), ("synthetic-b", "1")))
    assert first == second


def test_validation_is_fail_closed_and_drift_triggers_review():
    assert summarize_validation_outcomes([0] * 30, [0] * 30)["status"] == "INSUFFICIENT_SAMPLE"
    report = summarize_validation_outcomes([0, 1] * 15, [0, 1] * 15)
    assert report["status"] == "VALID" and report["sensitivity"] == 1.0
    drift = detect_numeric_drift([0, 1, 2, 3, 4] * 10, [100, 101, 102, 103, 104] * 10)
    assert drift["retraining_triggered"] is True
    assert detect_numeric_drift([0.1] * 5, [0.2] * 5)["status"] == "INSUFFICIENT_SAMPLE"


def test_multi_feature_drift_monitor_is_review_only_and_auditable():
    monitor = DriftMonitor(minimum_n=5, threshold=0.2)
    report = monitor.evaluate(
        model_id="synthetic-diabetes",
        model_version="1",
        reference={"hba1c": list(range(5)), "bmi": [20, 21, 22, 23, 24]},
        current={"hba1c": [100, 101, 102, 103, 104], "bmi": [20, 21, 22, 23, 24]},
    )
    assert report["status"] == "DRIFT"
    assert report["review_required"] is True
    assert report["action"] == "RETRAINING_REVIEW_REQUIRED"
    assert report["clinical_use_authorized"] is False
    assert report["schema_version"] == "wysh-ai-drift-review-v1"
    assert report["record_sha256"] and report["previous_record_sha256"] == "GENESIS"
    assert len(monitor.review_queue) == 1


def test_multi_feature_drift_monitor_rejects_mismatched_feature_sets():
    report = DriftMonitor(minimum_n=5).evaluate(model_id="m", model_version="1", reference={"a": [1] * 5}, current={"b": [1] * 5})
    assert report["status"] == "INVALID_DATA"
    assert report["review_required"] is False


def test_drift_monitor_rejects_replayed_evaluation_ids_and_chains_records():
    monitor = DriftMonitor(minimum_n=5)
    kwargs = {"model_id": "m", "model_version": "1", "reference": {"a": [1, 2, 3, 4, 5]}, "current": {"a": [1, 2, 3, 4, 5]}}
    first = monitor.evaluate(**kwargs, evaluation_id="eval-1")
    replay = monitor.evaluate(**kwargs, evaluation_id="eval-1")
    second = monitor.evaluate(**kwargs, evaluation_id="eval-2")
    assert first["status"] == "STABLE"
    assert replay["status"] == "REPLAY_REJECTED"
    assert second["previous_record_sha256"] == first["record_sha256"]
    assert len(monitor.review_queue) == 2


def test_explainability_and_audit_are_non_clinical_and_redacted():
    explanation = explain_linear_prediction(features={"hba1c": 7.0}, weights={"hba1c": 0.4})
    assert explanation["explainability_type"] == "NATIVE_LINEAR_ATTRIBUTION"
    assert explanation["shap_lime_status"] == "NOT_CONFIGURED"
    audit = InferenceAuditLog()
    record = audit.append(event_id="e1", model_id="m", model_version="1", input_payload={"synthetic": True}, output_payload={"draft": True}, status="COMPLETED")
    assert record.input_sha256 and record.output_sha256
    assert "synthetic" not in record.input_sha256 and "draft" not in record.output_sha256
