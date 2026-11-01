"""Local release gate for production isolation and synthetic scope boundaries."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def check(name: str, passed: bool) -> dict[str, object]:
    return {"check": name, "status": "PASS" if passed else "FAIL"}


def main() -> int:
    production = TestClient(create_app(Settings(environment="production", inference_enabled=True, service_token_secret="test-only")))
    payload = {"tenant_id": "synthetic-tenant", "patient_id": "synthetic-patient", "synthetic": True}
    decision = {**payload, "question": "Which queue should receive this intake?", "permitted_options": ["routine", "review"]}
    checks = [
        check("production snapshot inference disabled", production.post("/v1/snapshots", json=payload).status_code == 503),
        check("production decision inference disabled", production.post("/v1/decisions", json=decision).status_code == 503),
    ]
    development = TestClient(create_app(Settings()))
    checks.extend([
        check("real patient snapshot rejected", development.post("/v1/snapshots", json={**payload, "patient_id": "patient-real"}).status_code == 403),
        check("real tenant decision rejected", development.post("/v1/decisions", json={**decision, "tenant_id": "tenant-real"}).status_code == 403),
    ])
    payload_out = {"suite": "security-isolation-r1", "status": "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL", "checks": checks}
    output = Path(__file__).parents[3] / "artifacts" / "r1-test-evidence" / "security-gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload_out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), **payload_out}, indent=2))
    return 0 if payload_out["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
