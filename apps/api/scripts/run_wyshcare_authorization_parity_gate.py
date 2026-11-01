"""Verify synthetic WyshCare-to-wysh.AI authorization parity cases."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.auth import make_test_token  # noqa: E402
from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.trion import TrionResult  # noqa: E402
import app.main as main_module  # noqa: E402


SECRET = "synthetic-parity-secret"
TENANT = "synthetic-parity-tenant"
PATIENT = "synthetic-parity-patient"
SUBJECT = "synthetic-parity-clinician"


def request_payload(**updates: object) -> dict:
    payload = {
        "request_id": "parity-request-1",
        "correlation_id": "parity-correlation-1",
        "tenant_id": TENANT,
        "patient_id": PATIENT,
        "practitioner_subject": SUBJECT,
        "synthetic": True,
        "purpose_of_use": "synthetic-evaluation",
        "consent_id": "synthetic-parity-consent",
        "evidence": [{"evidence_id": "obs-1", "source_type": "fhir_observation", "recorded_at": "2026-10-24T00:00:00Z", "content_sha256": "a" * 64}],
        "requested_model": {"provider": "medgemma", "model_id": "medgemma:latest", "model_version": "synthetic"},
        "requested_rule_version": "diabetes-r1",
        "terminology_version": "synthetic-terminology-v1",
        "review_required": True,
        "clinical_use_authorized": False,
    }
    payload.update(updates)
    return payload


def token(**updates: object) -> str:
    claims = {
        "issuer": "wyshcare",
        "audience": "wysh-ai",
        "tenant_id": TENANT,
        "patient_ids": [PATIENT],
        "scopes": ["clinical-workflow:execute"],
        "roles": ["clinician"],
        "subject": SUBJECT,
        "purpose_of_use": "synthetic-evaluation",
        "consent_id": "synthetic-parity-consent",
    }
    claims.update(updates)
    return make_test_token(SECRET, **claims)


def trion_payload(**updates: object) -> dict:
    payload = {
        "tenant_id": TENANT,
        "patient_id": PATIENT,
        "document_id": "synthetic-trion-document",
        "practitioner_subject": SUBJECT,
        "purpose_of_use": "synthetic-evaluation",
        "consent_id": "synthetic-parity-consent",
        "synthetic": True,
        "facts": [{"statement": "Synthetic fact", "evidence": [{"source_id": "synthetic-1", "source_type": "observation", "recorded_at": "2026-10-24T00:00:00Z"}]}],
    }
    payload.update(updates)
    return payload


def main() -> int:
    client = TestClient(create_app(Settings(require_gateway_auth=True, service_token_secret=SECRET)))

    def post(payload: dict, auth: str | None = None, key: str = "parity-idem-1"):
        headers = {"Idempotency-Key": key}
        if auth is not None:
            headers["Authorization"] = f"Bearer {auth}"
        return client.post("/v1/integration/wyshcare/clinical-draft", headers=headers, json=payload)

    valid = post(request_payload(), token())
    replay = post(request_payload(), token(), "parity-idem-replay")
    replay_again = post(request_payload(), token(), "parity-idem-replay")
    conflict = post(request_payload(correlation_id="parity-conflict"), token(), "parity-idem-replay")

    def fake_trion_execute(self, request_payload, *, correlation_id=None, idempotency_key=None):
        return TrionResult("success", correlation_id or "synthetic-correlation", idempotency_key or "synthetic-idempotency", {"schemaVersion": 1, "documentId": request_payload["documentId"], "resources": [], "generatedBy": "TRION", "model": "synthetic-trion"})

    main_module.TrionClient.execute = fake_trion_execute
    trion_client = TestClient(create_app(Settings(require_gateway_auth=True, service_token_secret=SECRET, trion_enabled=True, trion_base_url="http://synthetic-trion.test", trion_api_key="synthetic-only")))

    def trion_post(payload: dict, auth: str | None = None, key: str = "trion-parity-1"):
        headers = {"Idempotency-Key": key}
        if auth is not None:
            headers["Authorization"] = f"Bearer {auth}"
        return trion_client.post("/v1/trion/fhir-draft", headers=headers, json=payload)

    trion_token = token(scopes=["trion:fhir-draft"])
    trion_valid = trion_post(trion_payload(), trion_token)
    trion_consent_denied = trion_post(trion_payload(consent_id="different-consent"), trion_token, "trion-parity-consent")
    trion_subject_denied = trion_post(trion_payload(practitioner_subject=None), trion_token, "trion-parity-subject")

    cases = [
        ("valid scoped clinician", valid.status_code == 200),
        ("missing token denied", post(request_payload(), None, "parity-missing").status_code == 401),
        ("wrong tenant denied", post(request_payload(), token(tenant_id="synthetic-other-tenant"), "parity-tenant").status_code == 401),
        ("wrong patient denied", post(request_payload(), token(patient_ids=["synthetic-other-patient"]), "parity-patient").status_code == 401),
        ("wrong purpose denied", post(request_payload(), token(purpose_of_use="different-purpose"), "parity-purpose").status_code == 403),
        ("wrong consent denied", post(request_payload(), token(consent_id="different-consent"), "parity-consent").status_code == 403),
        ("wrong practitioner denied", post(request_payload(), token(subject="synthetic-other-clinician"), "parity-subject").status_code == 403),
        ("non-clinician denied", post(request_payload(), token(roles=["administrator"]), "parity-role").status_code == 403),
        ("delegation omission denied", post(request_payload(), token(delegated_by="synthetic-supervisor"), "parity-delegation").status_code == 403),
        ("missing practitioner denied", post(request_payload(practitioner_subject=None), token(), "parity-missing-subject").status_code == 403),
        ("replay deterministic", replay.status_code == 200 and replay_again.status_code == 200 and replay.json() == replay_again.json()),
        ("conflicting replay rejected", conflict.status_code == 409),
        ("TRION valid scoped clinician", trion_valid.status_code == 200),
        ("TRION consent mismatch denied", trion_consent_denied.status_code == 403),
        ("TRION missing practitioner denied", trion_subject_denied.status_code == 403),
    ]
    report = {
        "schema_version": "wyshcare-authorization-parity-v1",
        "status": "PASS" if all(passed for _, passed in cases) else "FAIL",
        "synthetic_only": True,
        "clinical_use_authorized": False,
        "wyshcare_modified": False,
        "cases": [{"case": name, "status": "PASS" if passed else "FAIL"} for name, passed in cases],
    }
    output = ROOT / "artifacts/integration/wyshcare-authorization-parity.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(output)}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
