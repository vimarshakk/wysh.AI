"""Run a synthetic decision through the FastAPI gateway and local MedGemma."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def main() -> int:
    model = os.environ.get("MEDGEMMA_MODEL", "medgemma:latest")
    base = os.environ.get("MEDGEMMA_BASE_URL", "http://127.0.0.1:11434")
    settings = replace(
        Settings.from_sources(),
        inference_enabled=True,
        model_routing_order=("medgemma",),
        enabled_model_ids=frozenset({model}),
        medgemma_base_url=base,
        medgemma_model=model,
    )
    response = TestClient(create_app(settings)).post(
        "/v1/decisions",
        headers={"X-Correlation-Id": "synthetic-medgemma-decision"},
        json={
            "tenant_id": "synthetic-medgemma-tenant",
            "patient_id": "synthetic-medgemma-patient",
            "question": "Which administrative review queue should receive this intake?",
            "permitted_options": ["routine", "review"],
            "synthetic": True,
            "evidence": [{"source_id": "synthetic-medgemma-workflow", "source_type": "workflow", "recorded_at": "2026-01-01T00:00:00Z"}],
        },
    )
    body = response.json()
    checks = {
        "http_success": response.status_code == 200,
        "real_model_id": response.status_code == 200 and body.get("model_id") == model,
        "schema_provenance": response.status_code == 200 and body.get("provenance", {}).get("evidence_count") == 1,
        "human_review_required": response.status_code == 200 and body.get("human_review_required") is True,
        "clinical_use_disabled": response.status_code == 200 and body.get("clinical_use_authorized") is False,
        "synthetic_only": True,
    }
    payload = {"suite": "synthetic-medgemma-decision-e2e", "status": "PASS" if all(checks.values()) else "FAIL", "model_id": model, "abstained": body.get("abstained"), "checks": checks}
    output = Path(__file__).parents[3] / "artifacts" / "r1-test-evidence" / "medgemma-decision-e2e.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), **payload}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
