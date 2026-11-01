"""Run the cross-cutting synthetic safety contract harness.

This is a contract/integration harness, not a live-model evaluation. It never
relabels a fixture as model inference and writes only sanitized check results.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import make_test_token
from app.config import Settings
from app.decision import DecisionModelOutput
from app.main import create_app
from app.providers import InferenceTelemetry


ROOT = Path(__file__).parents[3]


def main() -> int:
    checks: dict[str, bool] = {}
    settings = Settings(service_token_secret="synthetic-e2e-secret")
    app = create_app(settings)
    client = TestClient(app)

    health = client.get("/health")
    patients = client.get("/v1/console/synthetic-patients")
    checks["health_is_non_authorizing"] = health.status_code == 200 and health.json().get("clinical_use_authorized") is False
    checks["synthetic_patient_workspace"] = patients.status_code == 200 and len(patients.json().get("patients", [])) >= 60

    decision = client.post(
        "/v1/decisions",
        json={
            "tenant_id": "synthetic-e2e-tenant", "patient_id": "synthetic-e2e-patient",
            "question": "Which administrative queue should receive this intake?",
            "permitted_options": ["routine", "review"], "synthetic": True,
        },
    )
    decision_body = decision.json()
    checks["missing_evidence_abstains"] = decision.status_code == 200 and decision_body.get("abstained") is True and decision_body.get("telemetry", {}).get("route_attempts") == []

    bridge = client.post(
        "/v1/integration/wyshcare/clinical-draft",
        headers={"Idempotency-Key": "synthetic-e2e-bridge"},
        json={
            "request_id": "synthetic-e2e-bridge-request", "correlation_id": "synthetic-e2e-bridge-correlation",
            "tenant_id": "synthetic-e2e-tenant", "patient_id": "synthetic-e2e-patient", "synthetic": True,
            "purpose_of_use": "synthetic-evaluation", "consent_id": "synthetic-consent",
            "evidence": [{"evidence_id": "obs-1", "source_type": "fhir_observation", "recorded_at": "2026-01-01T00:00:00Z", "content_sha256": "a" * 64}],
            "requested_model": {"provider": "medgemma", "model_id": "medgemma:latest"}, "review_required": True, "clinical_use_authorized": False,
        },
    )
    checks["bridge_is_typed_abstention"] = bridge.status_code == 200 and bridge.json().get("status") == "ABSTAINED" and bridge.json().get("clinical_use_authorized") is False

    trion = client.post(
        "/v1/trion/fhir-draft",
        json={"tenant_id": "synthetic-e2e-tenant", "patient_id": "synthetic-e2e-patient", "document_id": "synthetic-doc", "synthetic": True, "facts": [{"statement": "Synthetic fact", "evidence": [{"source_id": "obs-1", "source_type": "observation", "recorded_at": "2026-01-01T00:00:00Z"}]}]},
    )
    checks["trion_disabled_by_default"] = trion.status_code == 503

    token = make_test_token("synthetic-e2e-secret", issuer="wyshcare", audience="wysh-ai", tenant_id="synthetic-e2e-tenant", patient_ids=["synthetic-e2e-patient"], scopes=["clinical-review:read", "clinical-review:write"], roles=["clinician"], subject="synthetic-e2e-clinician")
    headers = {"Authorization": f"Bearer {token}"}
    review = client.post("/v1/clinical-reviews", headers=headers, json={"tenant_id": "synthetic-e2e-tenant", "patient_id": "synthetic-e2e-patient", "disease_id": "diabetes", "assessment_id": "synthetic-assessment", "assessment_input_hash": "b" * 64, "synthetic": True})
    review_body = review.json()
    approved = client.post(f"/v1/clinical-reviews/{review_body.get('review_id')}/decision", headers=headers, json={"tenant_id": "synthetic-e2e-tenant", "patient_id": "synthetic-e2e-patient", "expected_version": 1, "action": "approve", "synthetic": True}) if review.status_code == 201 else None
    checks["persistent_clinician_review"] = review.status_code == 201 and approved is not None and approved.status_code == 200 and approved.json().get("state") == "APPROVED" and len(approved.json().get("events", [])) == 2

    original_infer = __import__("app.main", fromlist=["ModelGateway"]).ModelGateway.infer
    try:
        def unsafe_fixture(*_args, **_kwargs):
            return DecisionModelOutput(selected_option="routine", rationale="Start medication immediately.", abstained=False), InferenceTelemetry("synthetic-fixture", "medgemma", "fixture", "success", 1, schema_validated=True)
        __import__("app.main", fromlist=["ModelGateway"]).ModelGateway.infer = unsafe_fixture
        unsafe_app = create_app(Settings(inference_enabled=True, enabled_model_ids=frozenset({"medgemma:latest"}), medgemma_model="medgemma:latest"))
        unsafe_response = TestClient(unsafe_app).post("/v1/decisions", json={"tenant_id": "synthetic-e2e-tenant", "patient_id": "synthetic-e2e-patient", "question": "Which administrative queue should receive this intake?", "permitted_options": ["routine", "review"], "synthetic": True, "evidence": [{"source_id": "obs-1", "source_type": "workflow", "recorded_at": "2026-01-01T00:00:00Z"}]})
        checks["unsafe_output_abstains"] = unsafe_response.status_code == 200 and unsafe_response.json().get("abstained") is True
    finally:
        __import__("app.main", fromlist=["ModelGateway"]).ModelGateway.infer = original_infer

    production = TestClient(create_app(Settings(environment="production", inference_enabled=True)))
    production_response = production.post("/v1/decisions", json={"tenant_id": "synthetic-e2e-tenant", "patient_id": "synthetic-e2e-patient", "question": "Which administrative queue should receive this intake?", "permitted_options": ["routine", "review"], "synthetic": True, "evidence": [{"source_id": "obs-1", "source_type": "workflow", "recorded_at": "2026-01-01T00:00:00Z"}]})
    checks["production_inference_disabled"] = production_response.status_code == 503
    metrics = client.get("/metrics").text
    checks["metrics_redacted"] = "synthetic-e2e-patient" not in metrics and "Authorization" not in metrics

    evidence = {
        "schema_version": "worldclass-synthetic-e2e-v1",
        "suite": "wysh-ai-cross-cutting-safety-contract",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "synthetic_only": True,
        "model_execution": "NOT_RUN_CONTRACT_HARNESS",
        "fixture_fallback_used": False,
        "clinical_use_authorized": False,
        "clinical_validation": "NO-GO",
        "production": "NO-GO",
        "wyshcare_modified": False,
    }
    output = ROOT / "artifacts" / "integration" / "worldclass-synthetic-e2e.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), **evidence}, indent=2))
    return 0 if evidence["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
