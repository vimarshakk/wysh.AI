from fastapi.testclient import TestClient
import pytest

from app.bridge_contracts import WyshCareAIBridgeRequest
from app.config import Settings
from app.main import create_app
from app.wyshcare_adapter import WyshCareBridgeClient, WyshCareBridgeError


def _request() -> WyshCareAIBridgeRequest:
    return WyshCareAIBridgeRequest.model_validate(
        {
            "request_id": "adapter-request-1",
            "correlation_id": "adapter-correlation-1",
            "tenant_id": "synthetic-tenant-1",
            "patient_id": "synthetic-patient-1",
            "practitioner_subject": "synthetic-clinician-1",
            "synthetic": True,
            "purpose_of_use": "synthetic-evaluation",
            "consent_id": "synthetic-consent-1",
            "evidence": [{
                "evidence_id": "obs-1",
                "source_type": "fhir_observation",
                "recorded_at": "2026-10-24T00:00:00Z",
                "content_sha256": "a" * 64,
            }],
            "requested_model": {
                "provider": "medgemma",
                "model_id": "medgemma:latest",
                "model_version": "synthetic",
            },
            "requested_rule_version": "diabetes-r1",
            "terminology_version": "synthetic-terminology-v1",
            "review_required": True,
            "clinical_use_authorized": False,
        }
    )


def test_adapter_consumes_typed_abstention_and_preserves_identity():
    server = TestClient(create_app(Settings()))
    captured: dict[str, object] = {}

    def transport(*, headers, json):
        captured.update({"headers": headers, "json": json})
        return server.post(
            "/v1/integration/wyshcare/clinical-draft",
            headers=dict(headers),
            json=dict(json),
        )

    result = WyshCareBridgeClient(transport).request_clinical_draft(
        _request(), idempotency_key="adapter-idem-1"
    )
    assert result.status == "ABSTAINED"
    assert result.review_required is True
    assert result.clinical_use_authorized is False
    assert captured["headers"] == {
        "Idempotency-Key": "adapter-idem-1",
        "X-Correlation-Id": "adapter-correlation-1",
    }


def test_adapter_reuses_request_identity_for_deterministic_replay():
    server = TestClient(create_app(Settings()))
    calls = 0

    def transport(*, headers, json):
        nonlocal calls
        calls += 1
        return server.post(
            "/v1/integration/wyshcare/clinical-draft",
            headers=dict(headers),
            json=dict(json),
        )

    adapter = WyshCareBridgeClient(transport)
    first = adapter.request_clinical_draft(_request())
    replay = adapter.request_clinical_draft(_request())
    assert first == replay
    assert calls == 2


def test_adapter_rejects_non_success_or_authorizing_response():
    class Response:
        status_code = 200

        def json(self):
            return {
                "schema_version": "wyshcare-ai-bridge-v1",
                "request_id": "adapter-request-1",
                "correlation_id": "adapter-correlation-1",
                "status": "COMPLETED_DRAFT",
                "reason": "unsafe",
                "model_id": "medgemma:latest",
                "model_version": "synthetic",
                "evidence_refs": ["obs-1"],
                "provenance_hash": "b" * 64,
                "review_required": True,
                "clinical_use_authorized": True,
            }

    with pytest.raises(WyshCareBridgeError, match="typed validation"):
        WyshCareBridgeClient(
            lambda **_: Response()
        ).request_clinical_draft(_request())


def test_adapter_rejects_non_synthetic_request_before_transport():
    request = _request()
    object.__setattr__(request, "synthetic", False)
    with pytest.raises(WyshCareBridgeError, match="synthetic requests only"):
        WyshCareBridgeClient(
            lambda **_: pytest.fail("transport must not be called")
        ).request_clinical_draft(request)
