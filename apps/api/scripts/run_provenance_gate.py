"""Run synthetic R2 provenance and contract invariants without contacting providers."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.decision import DecisionRequest, EvidenceReference, input_hash
from app.main import create_app


ROOT = Path(__file__).parents[3]


def _load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def main() -> int:
    fixture = _load("fixtures/synthetic/fhir/snapshot-bundle-v1.json")
    evaluation = _load("fixtures/synthetic/evaluation/r2-cases.json")
    app = create_app(Settings())
    client = TestClient(app)
    evidence = [{"source_id": "synthetic-observation-r2-001", "source_type": "observation", "recorded_at": "2026-01-01T00:10:00Z"}]
    payload = {
        "tenant_id": "synthetic-r2-tenant",
        "patient_id": "synthetic-patient-r2-001",
        "question": "Which queue should receive this intake?",
        "permitted_options": ["routine", "review"],
        "synthetic": True,
        "evidence": evidence,
    }
    response = client.post("/v1/decisions", headers={"X-Correlation-Id": "r2-provenance-gate"}, json=payload)
    request = DecisionRequest.model_validate(payload)
    altered = request.model_copy(update={"evidence": [EvidenceReference(source_id="synthetic-encounter-r2-001", source_type="encounter", recorded_at="2026-01-01T00:30:00Z")]})
    audit_json = json.dumps([event.redacted_dict() for event in app.state.audit_sink.events])
    checks = {
        "synthetic_fhir_bundle": fixture.get("resourceType") == "Bundle" and fixture.get("meta", {}).get("tag", [{}])[0].get("code") == "synthetic",
        "evaluation_manifest_is_synthetic": evaluation.get("synthetic_only") is True and len(evaluation.get("cases", [])) >= 4,
        "decision_contract_response": response.status_code == 200,
        "input_hash_is_deterministic": input_hash(request) == input_hash(request),
        "input_hash_changes_with_evidence": input_hash(request) != input_hash(altered),
        "response_provenance_preserves_evidence_count": response.status_code == 200 and response.json()["provenance"]["evidence_count"] == 1,
        "response_provenance_has_hash": response.status_code == 200 and len(response.json()["provenance"]["input_hash"]) == 64,
        "audit_does_not_contain_raw_subject_ids": "synthetic-r2-tenant" not in audit_json and "synthetic-patient-r2-001" not in audit_json,
    }
    payload_out = {"suite": "r2-provenance-gate", "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "synthetic_only": True}
    output = ROOT / "artifacts/r2-test-evidence/provenance-gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload_out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), **payload_out}, indent=2))
    return 0 if payload_out["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
