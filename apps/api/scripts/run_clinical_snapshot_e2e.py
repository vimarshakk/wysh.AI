"""Synthetic Clinical Snapshot -> typed decision E2E; never contacts a provider."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def main() -> int:
    client = TestClient(create_app(Settings()))
    tenant_id = "synthetic-e2e-tenant"
    patient_id = "synthetic-e2e-patient"
    snapshot = client.post(
        "/v1/snapshots",
        headers={"X-Correlation-Id": "synthetic-e2e-correlation"},
        json={
            "tenant_id": tenant_id,
            "patient_id": patient_id,
            "synthetic": True,
            "facts": [{"statement": "Synthetic intake requires routine review.", "evidence": [{"source_id": "synthetic-e2e-observation", "source_type": "observation", "recorded_at": "2026-01-01T00:00:00Z"}]}],
        },
    )
    decision = client.post(
        "/v1/decisions",
        headers={"X-Correlation-Id": "synthetic-e2e-decision"},
        json={
            "tenant_id": tenant_id,
            "patient_id": patient_id,
            "question": "Which queue should receive this intake?",
            "permitted_options": ["routine", "review"],
            "synthetic": True,
            "evidence": [{"source_id": "synthetic-e2e-observation", "source_type": "observation", "recorded_at": "2026-01-01T00:00:00Z"}],
        },
    )
    checks = {
        "snapshot_created": snapshot.status_code == 200,
        "decision_created": decision.status_code == 200,
        "decision_abstained_when_inference_disabled": decision.status_code == 200 and decision.json()["abstained"] is True,
        "evidence_provenance_preserved": decision.status_code == 200 and decision.json()["provenance"]["evidence_count"] == 1,
        "synthetic_only": True,
    }
    payload = {"suite": "synthetic-clinical-snapshot-e2e", "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}
    output = Path(__file__).parents[3] / "artifacts" / "r1-test-evidence" / "clinical-snapshot-e2e.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), **payload}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
