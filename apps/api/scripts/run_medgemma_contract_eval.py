"""Evaluate real local MedGemma against synthetic decision-contract cases only."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


CASES = (
    ("routine-intake", "Which administrative review queue should receive this intake?", ("routine", "review")),
    ("human-review-routing", "Which workflow queue should receive this case?", ("routine", "review")),
)


def main() -> int:
    model = os.environ.get("MEDGEMMA_MODEL", "medgemma:latest")
    settings = replace(Settings.from_sources(), inference_enabled=True, model_routing_order=("medgemma",), enabled_model_ids=frozenset({model}), medgemma_model=model)
    client = TestClient(create_app(settings))
    results = []
    for case_id, question, options in CASES:
        response = client.post(
            "/v1/decisions",
            headers={"X-Correlation-Id": f"synthetic-contract-{case_id}"},
            json={
                "tenant_id": "synthetic-medgemma-eval-tenant",
                "patient_id": f"synthetic-medgemma-{case_id}",
                "question": question,
                "permitted_options": list(options),
                "synthetic": True,
                "evidence": [{"source_id": f"synthetic-evidence-{case_id}", "source_type": "workflow", "recorded_at": "2026-01-01T00:00:00Z"}],
            },
        )
        body = response.json()
        passed = response.status_code == 200 and body.get("model_id") == model and (body.get("selected_option") in options or body.get("abstained") is True) and body.get("confidence") is None and body.get("provenance", {}).get("evidence_count") == 1 and body.get("human_review_required") is True and body.get("clinical_use_authorized") is False
        results.append({"case_id": case_id, "passed": passed, "http_status": response.status_code, "model_id": body.get("model_id"), "selected_option": body.get("selected_option"), "abstained": body.get("abstained"), "confidence_exposed": body.get("confidence") is not None})
    payload = {"suite": "synthetic-medgemma-contract-evaluation", "status": "PASS" if all(item["passed"] for item in results) else "FAIL", "model_id": model, "clinical_accuracy_claim": False, "results": results}
    output = Path(__file__).parents[3] / "artifacts" / "r1-test-evidence" / "medgemma-contract-evaluation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), **payload}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
