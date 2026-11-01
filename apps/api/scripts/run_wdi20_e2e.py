"""Synthetic WDI-20 catalog and Phase 1 longitudinal-monitoring E2E."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def main() -> int:
    root = Path(__file__).parents[3]
    client = TestClient(create_app(Settings()))
    catalog = client.get("/v1/disease-intelligence/catalog")
    monitoring = client.post("/v1/disease-intelligence/monitor", json={
        "tenant_id": "synthetic-wdi-e2e-tenant", "patient_id": "synthetic-wdi-e2e-patient", "disease_id": "diabetes", "synthetic": True,
        "measurements": [
            {"measurement_id": "glucose-1", "metric": "glucose", "value": 130, "unit": "mg/dL", "observed_at": "2026-01-01T00:00:00Z", "source_type": "observation"},
            {"measurement_id": "glucose-2", "metric": "glucose", "value": 120, "unit": "mg/dL", "observed_at": "2026-02-01T00:00:00Z", "source_type": "observation"},
        ],
    })
    rules = client.post("/v1/disease-intelligence/rules/evaluate", json={
        "tenant_id": "synthetic-wdi-e2e-tenant", "patient_id": "synthetic-wdi-e2e-patient", "disease_id": "diabetes", "synthetic": True,
        "measurements": [{"measurement_id": "hba1c-1", "metric": "hba1c", "value": 7.2, "unit": "%", "observed_at": "2026-01-01T00:00:00Z", "source_type": "laboratory"}],
    })
    body = monitoring.json()
    checks = {
        "wdi20_catalog": catalog.status_code == 200 and len(catalog.json()["catalog"]["conditions"]) == 20,
        "phase1_workflows": catalog.status_code == 200 and len(catalog.json()["phase1_workflows"]["workflows"]) == 6,
        "monitoring_response": monitoring.status_code == 200,
        "descriptive_trend": monitoring.status_code == 200 and body["interpretation_status"] == "DESCRIPTIVE_ONLY",
        "evidence_refs_preserved": monitoring.status_code == 200 and body["trends"][0]["evidence_refs"] == ["glucose-1", "glucose-2"],
        "clinical_use_disabled": monitoring.status_code == 200 and body["clinical_use_authorized"] is False,
        "deterministic_rules": rules.status_code == 200 and rules.json()["interpretation_status"] == "DETERMINISTIC_COMPLETENESS_ONLY",
    }
    payload = {"suite": "synthetic-wdi20-e2e", "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "synthetic_only": True}
    output = root / "artifacts/r2-test-evidence/wdi20-e2e.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), **payload}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
