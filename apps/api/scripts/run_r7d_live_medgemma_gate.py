"""Run the R7D workflow against the configured local MedGemma runtime.

This gate never replaces a missing or failing local model with a fixture. A
missing Ollama model is recorded as BLOCKED, not PASS.
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.providers import MedGemmaProvider  # noqa: E402


def synthetic_bundle() -> dict:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "meta": {"tag": [{"system": "https://wysh.ai/synthetic", "code": "synthetic"}]},
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "synthetic-r7d-patient"}},
            {"resource": {"resourceType": "Observation", "id": "glucose-r7d", "status": "final", "code": {"coding": [{"system": "http://loinc.org", "code": "2339-0", "display": "Glucose [Mass/volume] in Blood"}]}, "effectiveDateTime": "2026-10-01T09:00:00Z", "valueQuantity": {"value": 120, "unit": "mg/dL"}}},
            {"resource": {"resourceType": "Observation", "id": "a1c-r7d", "status": "final", "code": {"coding": [{"system": "http://loinc.org", "code": "4548-4", "display": "Hemoglobin A1c/Hemoglobin.total in Blood"}]}, "effectiveDateTime": "2026-10-01T09:00:00Z", "valueQuantity": {"value": 6.2, "unit": "%"}}},
        ],
    }


def main() -> int:
    requested_model = os.environ.get("MEDGEMMA_MODEL", "medgemma:latest")
    base_settings = Settings.from_sources()
    settings = replace(base_settings, inference_enabled=True, require_gateway_auth=False, model_routing_order=("medgemma",), enabled_model_ids=frozenset({requested_model}), medgemma_model=requested_model, provider_timeout_ms=max(base_settings.provider_timeout_ms, 60000), provider_max_retries=0)
    output = ROOT / "artifacts" / "r7-test-evidence" / "r7d-live-medgemma-gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if not MedGemmaProvider(settings).ready():
        evidence = {"milestone": "R7D", "status": "BLOCKED", "reason": "configured local MedGemma runtime/model was not ready", "model_id": requested_model, "synthetic_only": True, "fallback_used": False}
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 2

    response = TestClient(create_app(settings)).post("/v1/clinical-intelligence/synthetic-workflow", json={"tenant_id": "synthetic-r7d-tenant", "patient_id": "synthetic-r7d-patient", "bundle": synthetic_bundle(), "synthetic": True, "provider": "medgemma"})
    body = response.json()
    telemetry = body.get("model_telemetry") or {}
    workflow_status = body.get("status")
    stage_reasons = [item.get("reason") for item in body.get("stages", []) if item.get("name") == "medgemma_explanation"]
    checks = {
        "http_success": response.status_code == 200,
        "workflow_completed_draft": workflow_status == "COMPLETED_DRAFT",
        "real_medgemma_telemetry": telemetry.get("provider") == "medgemma" and telemetry.get("model") == requested_model,
        "upstream_cql_executed": body.get("cql_upstream", {}).get("status") == "EXECUTED_UPSTREAM_RUNTIME",
        "safety_passed": body.get("safety", {}).get("status") == "PASS",
        "clinical_use_disabled": body.get("clinical_use_authorized") is False,
        "synthetic_only": body.get("synthetic_only") is True,
        "no_fallback": True,
    }
    gate_status = "PASS" if all(checks.values()) else ("BLOCKED" if workflow_status == "MODEL_UNAVAILABLE" else "FAIL")
    evidence = {"milestone": "R7D", "status": gate_status, "model_id": requested_model, "configured_model_version": settings.medgemma_model_version, "checks": checks, "workflow_status": workflow_status, "model_stage_reasons": stage_reasons, "safety_findings": body.get("safety", {}).get("findings", []), "latency_ms": telemetry.get("latency_ms"), "schema_validated": telemetry.get("schema_validated"), "synthetic_only": True, "fallback_used": False}
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["status"] == "PASS" else (2 if evidence["status"] == "BLOCKED" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
