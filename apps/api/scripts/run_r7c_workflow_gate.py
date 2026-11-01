"""Run the R7C synthetic workflow and review persistence acceptance gate."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth import make_test_token  # noqa: E402
from app.clinical_orchestration import ClinicalExplanation  # noqa: E402
from app.config import Settings  # noqa: E402
from app.gateway import ModelGateway  # noqa: E402
from app.main import create_app  # noqa: E402
from app.providers import InferenceTelemetry  # noqa: E402
from app.review_store import ReviewStore  # noqa: E402


TENANT = "synthetic-r7c-gate-tenant"
PATIENT = "synthetic-r7c-gate-patient"


def bundle() -> dict:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "meta": {"tag": [{"system": "https://wysh.ai/synthetic", "code": "synthetic"}]},
        "entry": [
            {"resource": {"resourceType": "Patient", "id": PATIENT}},
            {"resource": {"resourceType": "Observation", "id": "glucose-gate", "status": "final", "code": {"coding": [{"system": "http://loinc.org", "code": "2339-0", "display": "Glucose [Mass/volume] in Blood"}]}, "effectiveDateTime": "2026-10-01T09:00:00Z", "valueQuantity": {"value": 120, "unit": "mg/dL"}}},
            {"resource": {"resourceType": "Observation", "id": "a1c-gate", "status": "final", "code": {"coding": [{"system": "http://loinc.org", "code": "4548-4", "display": "Hemoglobin A1c/Hemoglobin.total in Blood"}]}, "effectiveDateTime": "2026-10-01T09:00:00Z", "valueQuantity": {"value": 6.2, "unit": "%"}}},
        ],
    }


def main() -> int:
    settings = Settings(service_token_secret="r7c-gate-secret", inference_enabled=True, enabled_model_ids=frozenset({"medgemma:latest"}), medgemma_model="medgemma:latest")
    app = create_app(settings)
    app.state.review_store.close()
    app.state.review_store = ReviewStore(":memory:")

    original_infer = ModelGateway.infer

    def synthetic_model(self, requested_provider, prompt, output_schema, *, system_prompt=None):
        result = ClinicalExplanation(summary="Synthetic evidence is available for clinician review; no clinical conclusion is made.", evidence_refs=["glucose-gate", "a1c-gate"], limitations=["Engineering-only synthetic workflow."] , abstained=False)
        return result, InferenceTelemetry("r7c-gate-model", "medgemma", "medgemma:latest", "success", 1, schema_validated=True)

    ModelGateway.infer = synthetic_model  # type: ignore[method-assign]
    try:
        client = TestClient(app)
        workflow = client.post("/v1/clinical-intelligence/synthetic-workflow", json={"tenant_id": TENANT, "patient_id": PATIENT, "bundle": bundle(), "synthetic": True, "provider": "medgemma"})
        if workflow.status_code != 200:
            raise RuntimeError(f"workflow HTTP {workflow.status_code}")
        workflow_body = workflow.json()
        token = make_test_token("r7c-gate-secret", issuer="wyshcare", audience="wysh-ai", tenant_id=TENANT, patient_ids=[PATIENT], scopes=["clinical-review:write", "clinical-review:read"], roles=["clinician"], subject="synthetic-r7c-clinician")
        headers = {"Authorization": f"Bearer {token}"}
        review = client.post("/v1/clinical-reviews", headers=headers, json={"tenant_id": TENANT, "patient_id": PATIENT, "disease_id": "diabetes", "assessment_id": workflow_body["workflow_id"], "assessment_input_hash": workflow_body["provenance_hash"], "synthetic": True})
        if review.status_code != 201:
            raise RuntimeError(f"review create HTTP {review.status_code}")
        review_body = review.json()
        approved = client.post(f"/v1/clinical-reviews/{review_body['review_id']}/decision", headers=headers, json={"tenant_id": TENANT, "patient_id": PATIENT, "expected_version": 1, "action": "approve", "synthetic": True})
        if approved.status_code != 200 or approved.json()["state"] != "APPROVED":
            raise RuntimeError(f"review decision HTTP {approved.status_code}")
        evidence = {
            "milestone": "R7C",
            "status": "PASS",
            "scope": "synthetic local engineering only",
            "workflow_status": workflow_body["status"],
            "stage_statuses": {item["name"]: item["status"] for item in workflow_body["stages"]},
            "cql_upstream_status": workflow_body["cql_upstream"]["status"],
            "safety_status": workflow_body["safety"]["status"],
            "review_state": approved.json()["state"],
            "review_event_count": len(approved.json()["events"]),
            "clinical_use_authorized": workflow_body["clinical_use_authorized"],
            "synthetic_only": workflow_body["synthetic_only"],
            "provider_mode": "typed synthetic model contract; real MedGemma availability is reported separately by /v1/providers/medgemma/ready",
        }
        output = ROOT / "artifacts" / "r7-test-evidence" / "r7c-workflow-gate.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 0
    finally:
        ModelGateway.infer = original_infer  # type: ignore[method-assign]


if __name__ == "__main__":
    raise SystemExit(main())
