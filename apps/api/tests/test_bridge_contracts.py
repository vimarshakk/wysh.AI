import pytest
from pydantic import ValidationError

from app.bridge_contracts import WyshAIBridgeResult, WyshCareAIBridgeRequest


def _request() -> dict:
    return {
        "request_id": "bridge-request-1",
        "correlation_id": "bridge-correlation-1",
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


def test_bridge_request_is_typed_and_synthetic_only():
    request = WyshCareAIBridgeRequest.model_validate(_request())
    assert request.synthetic is True
    assert request.review_required is True
    assert request.clinical_use_authorized is False


@pytest.mark.parametrize("field,value", [("tenant_id", "tenant-real"), ("patient_id", "patient-real"), ("consent_id", "")])
def test_bridge_request_rejects_scope_or_consent_boundary(field, value):
    payload = _request()
    payload[field] = value
    with pytest.raises(ValidationError):
        WyshCareAIBridgeRequest.model_validate(payload)


def test_bridge_result_rejects_duplicate_evidence_refs_and_authorization():
    with pytest.raises(ValidationError):
        WyshAIBridgeResult(request_id="r", correlation_id="c", status="COMPLETED_DRAFT", reason="test", model_id="m", provenance_hash="b" * 64, evidence_refs=["obs-1", "obs-1"])
    with pytest.raises(ValidationError):
        WyshAIBridgeResult(request_id="r", correlation_id="c", status="COMPLETED_DRAFT", reason="test", model_id="m", provenance_hash="b" * 64, clinical_use_authorized=True)
