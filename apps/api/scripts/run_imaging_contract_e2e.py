"""Synthetic imaging contract E2E; no image bytes or model endpoint are used."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def main() -> int:
    root = Path(__file__).parents[3]
    fixture = json.loads((root / "fixtures/synthetic/imaging/synthetic-xray-study-v1.json").read_text(encoding="utf-8"))
    response = TestClient(create_app(Settings())).post("/v1/imaging/analyze", json=fixture)
    body = response.json()
    checks = {
        "synthetic_fixture": fixture["synthetic"] is True and fixture["study"]["synthetic"] is True,
        "metadata_only": "image_bytes" not in fixture and "data" not in fixture["study"],
        "contract_response": response.status_code == 200,
        "fail_closed": response.status_code == 200 and body["status"] == "ABSTAINED" and body["findings"] == [],
        "human_review_required": response.status_code == 200 and body["human_review_required"] is True,
        "clinical_use_disabled": response.status_code == 200 and body["clinical_use_authorized"] is False,
    }
    payload = {"suite": "synthetic-imaging-contract-e2e", "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "synthetic_only": True}
    output = root / "artifacts/r2-test-evidence/imaging-contract-e2e.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), **payload}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
