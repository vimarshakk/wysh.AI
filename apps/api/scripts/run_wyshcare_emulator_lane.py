"""Run the isolated synthetic WyshCare -> wysh.AI bridge lane."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.config import Settings  # noqa: E402
from app.bridge_contracts import WyshCareAIBridgeRequest  # noqa: E402
from app.main import create_app  # noqa: E402
from app.wyshcare_adapter import WyshCareBridgeClient, WyshCareBridgeError  # noqa: E402


def payload() -> dict:
    return {
        "request_id": "emulator-request-1",
        "correlation_id": "emulator-correlation-1",
        "tenant_id": "synthetic-tenant-1",
        "patient_id": "synthetic-patient-1",
        "practitioner_subject": "synthetic-clinician-1",
        "synthetic": True,
        "purpose_of_use": "synthetic-evaluation",
        "consent_id": "synthetic-consent-1",
        "evidence": [{"evidence_id": "obs-1", "source_type": "fhir_observation", "recorded_at": "2026-10-24T00:00:00Z", "content_sha256": "a" * 64}],
        "requested_model": {"provider": "medgemma", "model_id": "medgemma:latest", "model_version": "synthetic"},
        "requested_rule_version": "diabetes-r1",
        "terminology_version": "synthetic-terminology-v1",
        "review_required": True,
        "clinical_use_authorized": False,
    }


def main() -> int:
    server = TestClient(create_app(Settings()))

    def transport(*, headers, json):
        return server.post("/v1/integration/wyshcare/clinical-draft", headers=dict(headers), json=dict(json))

    adapter = WyshCareBridgeClient(transport)
    request = WyshCareAIBridgeRequest.model_validate(payload())
    try:
        first = adapter.request_clinical_draft(request, idempotency_key="emulator-idem-1")
        replay = adapter.request_clinical_draft(request, idempotency_key="emulator-idem-1")
        conflicting = request.model_copy(update={"correlation_id": "emulator-conflict"})
        conflict_response = server.post(
            "/v1/integration/wyshcare/clinical-draft",
            headers={"Idempotency-Key": "emulator-idem-1"},
            json=conflicting.model_dump(mode="json"),
        )
        adapter_status = "PASS"
    except WyshCareBridgeError:
        first = replay = None
        conflict_response = None
        adapter_status = "FAIL"
    report = {
        "schema_version": "wyshcare-ai-emulator-lane-v1",
        "status": "PASS" if adapter_status == "PASS" and first == replay and conflict_response is not None and conflict_response.status_code == 409 else "FAIL",
        "synthetic_only": True,
        "clinical_use_authorized": False,
        "wyshcare_modified": False,
        "checks": [
            {"check": "typed adapter request", "status": "PASS" if adapter_status == "PASS" else "FAIL"},
            {"check": "idempotent replay", "status": "PASS" if adapter_status == "PASS" and first == replay else "FAIL"},
            {"check": "conflicting identity rejected", "status": "PASS" if conflict_response is not None and conflict_response.status_code == 409 else "FAIL", "status_code": conflict_response.status_code if conflict_response is not None else None},
            {"check": "explicit abstention", "status": "PASS" if first is not None and first.status == "ABSTAINED" else "FAIL"},
        ],
    }
    output = ROOT / "artifacts/integration/wyshcare-emulator-lane.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(output)}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
