"""Run the synthetic WyshCare↔wysh.AI bridge contract gate."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from pydantic import ValidationError
from fastapi.testclient import TestClient

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.bridge_contracts import WyshCareAIBridgeRequest  # noqa
from app.config import Settings  # noqa
from app.main import create_app  # noqa


def payload() -> dict:
    return {"request_id": "bridge-gate-request", "correlation_id": "bridge-gate-correlation", "tenant_id": "synthetic-tenant", "patient_id": "synthetic-patient", "synthetic": True, "purpose_of_use": "synthetic-evaluation", "consent_id": "synthetic-consent", "evidence": [{"evidence_id": "obs-1", "source_type": "fhir_observation", "recorded_at": "2026-10-24T00:00:00Z", "content_sha256": "a" * 64}], "requested_model": {"provider": "medgemma", "model_id": "medgemma:latest"}, "review_required": True, "clinical_use_authorized": False}  # noqa


def main() -> int:
    checks = []
    request = WyshCareAIBridgeRequest.model_validate(payload())
    checks.append({"check": "valid synthetic request", "status": "PASS", "review_required": request.review_required})
    response = TestClient(create_app(Settings())).post("/v1/integration/wyshcare/clinical-draft", json=payload())
    checks.append({"check": "executable bridge returns abstention", "status": "PASS" if response.status_code == 200 and response.json().get("status") == "ABSTAINED" else "FAIL", "http_status": response.status_code})
    for name, field, value in (("real tenant rejected", "tenant_id", "tenant-real"), ("real patient rejected", "patient_id", "patient-real")):
        candidate = payload()
        candidate[field] = value
        try:
            WyshCareAIBridgeRequest.model_validate(candidate)
        except ValidationError:
            checks.append({"check": name, "status": "PASS"})
        else:
            checks.append({"check": name, "status": "FAIL"})
    report = {"schema_version": "wyshcare-ai-bridge-gate-v1", "status": "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL", "synthetic_only": True, "clinical_use_authorized": False, "wyshcare_modified": False, "checks": checks}
    output = ROOT / "artifacts/integration/wyshcare-ai-bridge-gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(output)}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
