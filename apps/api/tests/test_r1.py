from __future__ import annotations

import json
import base64
import time

import pytest
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.config import Settings
from app.auth import make_test_token, verify_bearer_token
from app.decision import DecisionModelOutput
from app.evaluation import DEFAULT_CASES, evaluate
from app.gateway import ModelGateway
from app.main import create_app
from app.providers import GeminiProvider, MedGemmaProvider, OpenAICompatibleProvider, ProviderError
from app.trion import TrionClient, TrionError
from app.trion import TrionResult


def test_r2_contract_artifacts_are_synthetic_and_versioned():
    from pathlib import Path

    root = Path(__file__).parents[3]
    snapshot = json.loads((root / "packages/contracts/clinical-snapshot-v1.schema.json").read_text())
    review = json.loads((root / "packages/contracts/clinician-review-action-v1.schema.json").read_text())
    fhir = json.loads((root / "fixtures/synthetic/fhir/snapshot-bundle-v1.json").read_text())
    cases = json.loads((root / "fixtures/synthetic/evaluation/r2-cases.json").read_text())
    assert snapshot["$id"].endswith("clinical-snapshot-v1.schema.json")
    assert review["$id"].endswith("clinician-review-action-v1.schema.json")
    assert snapshot["properties"]["synthetic"]["const"] is True
    assert review["properties"]["from_state"]["const"] == "DRAFT"
    assert fhir["resourceType"] == "Bundle"
    assert fhir["meta"]["tag"][0]["code"] == "synthetic"
    assert cases["synthetic_only"] is True
    assert any(case["expected"].get("abstained") is True for case in cases["cases"])
    assert any(case["expected"].get("policy_denied") is True for case in cases["cases"])


def test_r2_provenance_gate_invariants():
    from app.decision import DecisionRequest, EvidenceReference, input_hash

    request = DecisionRequest(
        tenant_id="synthetic-r2-tenant", patient_id="synthetic-r2-patient", question="Which queue should receive this intake?",
        permitted_options=["routine", "review"], synthetic=True,
        evidence=[EvidenceReference(source_id="synthetic-observation", source_type="observation", recorded_at="2026-01-01T00:00:00Z")],
    )
    changed = request.model_copy(update={"evidence": [EvidenceReference(source_id="synthetic-encounter", source_type="encounter", recorded_at="2026-01-01T00:00:00Z")]})
    assert input_hash(request) == input_hash(request)
    assert input_hash(request) != input_hash(changed)


def test_capability_catalog_is_shared_and_not_clinically_authorized():
    response = TestClient(create_app(Settings())).get("/v1/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["clinical_use_authorized"] is False
    profile_ids = {profile["id"] for profile in body["profiles"]}
    assert {"patient-companion", "clinician-copilot", "care-navigation", "operations", "research"} <= profile_ids


def test_knowledge_grounding_returns_citations_and_abstains_without_match():
    client = TestClient(create_app(Settings()))
    base = {
        "tenant_id": "synthetic-knowledge-tenant",
        "patient_id": "synthetic-knowledge-patient",
        "synthetic": True,
        "chunks": [{"chunk_id": "chunk-1", "source_id": "synthetic-doc-1", "source_type": "document", "recorded_at": "2026-01-01T00:00:00Z", "title": "Routine intake workflow", "text": "Routine intake should be routed to the review queue."}],
    }
    grounded = client.post("/v1/knowledge/ground", json={**base, "question": "Where should routine intake be routed?"})
    assert grounded.status_code == 200
    assert grounded.json()["abstained"] is False
    assert grounded.json()["hits"][0]["source_id"] == "synthetic-doc-1"
    abstained = client.post("/v1/knowledge/ground", json={**base, "question": "What is the diagnosis?"})
    assert abstained.status_code == 200
    assert abstained.json()["abstained"] is True
    assert abstained.json()["hits"] == []


def test_patient_profile_cannot_use_workflow_decision_capability():
    from pydantic import ValidationError
    from app.decision import DecisionRequest

    with pytest.raises(ValidationError):
        DecisionRequest(
            tenant_id="synthetic-tenant", patient_id="synthetic-patient", question="Which queue should receive this intake?",
            permitted_options=["routine", "review"], synthetic=True, application_profile="patient-companion",
        )


def test_imaging_contract_is_metadata_only_and_fail_closed():
    client = TestClient(create_app(Settings()))
    response = client.post(
        "/v1/imaging/analyze",
        headers={"X-Correlation-Id": "synthetic-imaging-correlation"},
        json={
            "tenant_id": "synthetic-imaging-tenant", "patient_id": "synthetic-imaging-patient", "synthetic": True,
            "application_profile": "research", "task": "report_draft",
            "study": {
                "study_id": "synthetic-study", "image_id": "synthetic-image", "modality": "XR", "content_type": "image/dicom",
                "content_sha256": "a" * 64, "width": 2048, "height": 2048, "synthetic": True,
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ABSTAINED"
    assert body["findings"] == []
    assert body["clinical_use_authorized"] is False
    assert len(body["provenance"]["input_hash"]) == 64


def test_imaging_report_draft_composes_only_from_typed_observations():
    client = TestClient(create_app(Settings()))
    response = client.post(
        "/v1/imaging/analyze",
        json={
            "tenant_id": "synthetic-imaging-tenant", "patient_id": "synthetic-imaging-patient", "synthetic": True,
            "task": "report_draft",
            "study": {"study_id": "synthetic-study-report", "image_id": "synthetic-image-report", "modality": "XR", "content_type": "image/dicom", "content_sha256": "b" * 64, "width": 1024, "height": 1024, "synthetic": True},
            "observations": [{"label": "Synthetic opacity", "body_region": "left lung", "laterality": "left", "certainty": "uncertain", "evidence_ref": "synthetic-region-1"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["report"]["draft_only"] is True
    assert body["report"]["evidence_refs"] == ["synthetic-region-1"]
    assert body["clinical_use_authorized"] is False


def test_segmentation_prompt_creates_a_reviewable_job_without_a_mask():
    client = TestClient(create_app(Settings()))
    response = client.post(
        "/v1/imaging/analyze",
        json={
            "tenant_id": "synthetic-imaging-tenant", "patient_id": "synthetic-imaging-patient", "synthetic": True,
            "application_profile": "research", "task": "segmentation_draft",
            "study": {"study_id": "synthetic-study-seg", "image_id": "synthetic-image-seg", "modality": "CT", "content_type": "image/dicom", "content_sha256": "c" * 64, "width": 512, "height": 512, "synthetic": True},
            "segmentation_prompts": [{"prompt_type": "point", "coordinates": [0.5, 0.5], "text": None}, {"prompt_type": "text", "coordinates": [], "text": "synthetic organ"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["segmentation"]["status"] == "QUEUED"
    assert body["segmentation"]["prompt_types"] == ["point", "text"]
    assert body["segmentation"]["mask_references"] == []


def test_imaging_contract_rejects_non_synthetic_or_non_sha256_content():
    from pydantic import ValidationError
    from app.imaging import ImagingAnalysisRequest

    with pytest.raises(ValidationError):
        ImagingAnalysisRequest.model_validate({
            "tenant_id": "synthetic-tenant", "patient_id": "synthetic-patient", "synthetic": True, "task": "quality_check",
            "study": {"study_id": "s", "image_id": "i", "modality": "XR", "content_type": "image/dicom", "content_sha256": "not-a-digest", "synthetic": True},
        })


def test_open_source_ledger_blocks_unverified_projects_from_promotion():
    from pathlib import Path

    root = Path(__file__).parents[3]
    ledger = json.loads((root / "packages/contracts/open-source-adoption-v1.json").read_text())
    assert ledger["third_party_code_copied"] is False
    assert ledger["model_weights_copied"] is False
    assert all(item["integration_mode"] in {"adapter-only", "reference-only"} for item in ledger["projects"])
    assert all(not item["code_license_verified"] or item["promotion_status"] not in {"runtime", "approved"} for item in ledger["projects"])


def test_wdi20_catalog_and_phase1_workflows_are_versioned():
    client = TestClient(create_app(Settings()))
    response = client.get("/v1/disease-intelligence/catalog")
    assert response.status_code == 200
    body = response.json()
    assert len(body["catalog"]["conditions"]) == 20
    assert body["catalog"]["clinical_use_authorized"] is False
    assert len(body["phase1_workflows"]["workflows"]) == 6
    assert {item["disease_id"] for item in body["phase1_workflows"]["workflows"]} == {"diabetes", "prediabetes", "hypertension", "dyslipidemia", "obesity", "chronic-kidney-disease"}


def test_wdi_monitoring_returns_descriptive_trends_only():
    client = TestClient(create_app(Settings()))
    response = client.post(
        "/v1/disease-intelligence/monitor",
        json={
            "tenant_id": "synthetic-wdi-tenant", "patient_id": "synthetic-wdi-patient", "disease_id": "diabetes", "synthetic": True,
            "measurements": [
                {"measurement_id": "m1", "metric": "hba1c", "value": 7.4, "unit": "%", "observed_at": "2026-01-01T00:00:00Z", "source_type": "laboratory"},
                {"measurement_id": "m2", "metric": "hba1c", "value": 7.1, "unit": "%", "observed_at": "2026-04-01T00:00:00Z", "source_type": "laboratory"},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["trends"][0]["direction"] == "DOWN"
    assert body["trends"][0]["evidence_refs"] == ["m1", "m2"]
    assert body["interpretation_status"] == "DESCRIPTIVE_ONLY"
    assert body["clinical_use_authorized"] is False
    assert "risk" in body["rationale"]


def test_wdi_monitoring_rejects_phase_two_without_workflow_definition():
    client = TestClient(create_app(Settings()))
    response = client.post(
        "/v1/disease-intelligence/monitor",
        json={"tenant_id": "synthetic-wdi-tenant", "patient_id": "synthetic-wdi-patient", "disease_id": "anemia", "synthetic": True, "measurements": [{"measurement_id": "m1", "metric": "hemoglobin", "value": 12, "unit": "g/dL", "observed_at": "2026-01-01T00:00:00Z", "source_type": "laboratory"}]},
    )
    assert response.status_code == 422


def test_wdi_deterministic_rules_report_missing_data_without_diagnosis():
    client = TestClient(create_app(Settings()))
    response = client.post(
        "/v1/disease-intelligence/rules/evaluate",
        json={
            "tenant_id": "synthetic-rules-tenant", "patient_id": "synthetic-rules-patient", "disease_id": "diabetes", "synthetic": True,
            "measurements": [{"measurement_id": "glucose-1", "metric": "glucose", "value": 120, "unit": "mg/dL", "observed_at": "2026-01-01T00:00:00Z", "source_type": "laboratory"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["interpretation_status"] == "DETERMINISTIC_COMPLETENESS_ONLY"
    assert any(item["status"] == "MISSING_DATA" and "hba1c" in item["missing_metrics"] for item in body["findings"])
    assert body["review_required"] is True
    assert body["clinical_use_authorized"] is False


def test_synthetic_fhir_observations_map_to_wdi_monitoring():
    client = TestClient(create_app(Settings()))
    response = client.post(
        "/v1/disease-intelligence/fhir/monitor",
        json={
            "tenant_id": "synthetic-fhir-tenant", "patient_id": "synthetic-fhir-patient", "disease_id": "diabetes", "synthetic": True,
            "bundle": {
                "resourceType": "Bundle", "type": "collection", "meta": {"tag": [{"code": "synthetic"}]},
                "entry": [{"resource": {"resourceType": "Observation", "id": "obs-hba1c", "code": {"coding": [{"code": "4548-4"}]}, "effectiveDateTime": "2026-01-01T00:00:00Z", "valueQuantity": {"value": 7.2, "unit": "%"}}}],
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["trends"][0]["metric"] == "hba1c"
    assert body["trends"][0]["evidence_refs"] == ["obs-hba1c"]
    assert body["clinical_use_authorized"] is False


def test_decision_abstains_when_inference_disabled():
    app = create_app(Settings())
    client = TestClient(app)
    response = client.post(
        "/v1/decisions",
        json={"tenant_id": "synthetic-tenant", "patient_id": "synthetic-patient", "question": "Which queue should receive this intake?", "permitted_options": ["routine", "review"], "synthetic": True},
    )
    assert response.status_code == 200
    assert response.json()["abstained"] is True
    assert response.json()["confidence"] is None
    body = response.json()
    assert len(body["provenance"]["input_hash"]) == 64
    assert body["provenance"]["evidence_count"] == 0
    assert body["telemetry"]["status"] == "policy_abstained"
    assert body["telemetry"]["provider"] == "policy"
    assert body["telemetry"]["route_attempts"] == []
    assert len(app.state.audit_sink.events) == 1
    assert app.state.audit_sink.events[0].event_type == "decision.abstained"


def test_decision_replay_is_idempotent_and_conflicting_content_is_rejected():
    app = create_app(Settings())
    client = TestClient(app)
    base = {"tenant_id": "synthetic-tenant", "patient_id": "synthetic-patient", "question": "Which queue should receive this intake?", "permitted_options": ["routine", "review"], "synthetic": True}
    first = client.post("/v1/decisions", headers={"Idempotency-Key": "decision-idem-1"}, json=base)
    replay = client.post("/v1/decisions", headers={"Idempotency-Key": "decision-idem-1"}, json=base)
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    conflict = client.post("/v1/decisions", headers={"Idempotency-Key": "decision-idem-1"}, json={**base, "question": "Which administrative queue should receive this intake?"})
    assert conflict.status_code == 409
    assert len(app.state.audit_sink.events) == 1


def test_correlation_id_is_returned_without_logging_request_content():
    client = TestClient(create_app(Settings()))
    response = client.get("/health", headers={"X-Correlation-Id": "corr-test-1"})
    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"] == "corr-test-1"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_invalid_correlation_id_is_replaced_before_response_or_audit():
    app = create_app(Settings())
    response = TestClient(app).get("/health", headers={"X-Correlation-Id": "patient=synthetic-patient"})
    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"] != "patient=synthetic-patient"
    assert len(response.headers["X-Correlation-Id"]) == 36


def test_model_registry_is_typed_and_does_not_expose_secrets():
    client = TestClient(create_app(Settings()))
    response = client.get("/v1/models")
    assert response.status_code == 200
    body = response.json()
    assert body["default_mode"] == "disabled"
    assert any(item["id"] == "gemini-2.5-flash" and item["runtime_enabled"] is False for item in body["models"])
    assert "API_KEY" not in json.dumps(body)


def test_packaged_registry_matches_source_registry(monkeypatch, tmp_path):
    from pathlib import Path
    from app.registry import load_registry

    source = load_registry(Path(__file__).parents[2] / ".." / "packages" / "contracts" / "model-registry.json")
    packaged = load_registry(Path(__file__).parents[1] / "app" / "model-registry.json")
    assert source.model_dump() == packaged.model_dump()
    monkeypatch.setattr("app.registry.default_registry_path", lambda: tmp_path / "registry-not-mounted.json")
    assert load_registry().model_dump() == packaged.model_dump()


def test_evidence_and_provenance_are_typed_and_redacted():
    app = create_app(Settings())
    client = TestClient(app)
    response = client.post(
        "/v1/decisions",
        headers={"X-Correlation-Id": "corr-evidence"},
        json={
            "tenant_id": "synthetic-tenant",
            "patient_id": "synthetic-patient",
            "question": "Which queue should receive this intake?",
            "permitted_options": ["routine", "review"],
            "synthetic": True,
            "context": {"tenant_id": "synthetic-tenant", "patient_id": "synthetic-patient", "private_note": "do not persist"},
            "evidence": [{"source_id": "synthetic-workflow-1", "source_type": "workflow", "recorded_at": "2026-01-01T00:00:00Z", "locator": "case-1"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["evidence_refs"] == ["synthetic-workflow-1"]
    assert body["provenance"]["correlation_id"] == "corr-evidence"
    assert "private_note" not in json.dumps(app.state.audit_sink.events[0].redacted_dict())
    audit_json = json.dumps(app.state.audit_sink.events[0].redacted_dict())
    assert "synthetic-tenant" not in audit_json
    assert "synthetic-patient" not in audit_json
    assert app.state.audit_sink.events[0].tenant_id.startswith("audit-")
    assert app.state.audit_sink.events[0].subject.startswith("audit-")


def test_non_abstaining_output_without_evidence_is_forced_to_abstain():
    from app.decision import DecisionRequest, validate_output

    request = DecisionRequest(tenant_id="synthetic-tenant", patient_id="synthetic-patient", question="Which queue should receive this intake?", permitted_options=["routine", "review"], synthetic=True)
    output = validate_output(DecisionModelOutput(selected_option="routine", rationale="Unsupported fixture.", abstained=False, confidence=0.99), request)
    assert output.abstained is True
    assert output.selected_option is None
    assert output.confidence is None


def test_decision_context_rejects_nested_or_unbounded_raw_document_payloads():
    from pydantic import ValidationError
    from app.decision import DecisionRequest

    with pytest.raises(ValidationError):
        DecisionRequest(tenant_id="synthetic-tenant", patient_id="synthetic-patient", question="Which queue should receive this intake?", permitted_options=["routine", "review"], synthetic=True, context={"document": {"raw": "text"}})
    with pytest.raises(ValidationError):
        DecisionRequest(tenant_id="synthetic-tenant", patient_id="synthetic-patient", question="Which queue should receive this intake?", permitted_options=["routine", "review"], synthetic=True, context={"note": "x" * 501})


def test_missing_evidence_abstains_before_provider_call(monkeypatch):
    app = create_app(Settings(inference_enabled=True, gemini_api_key="test-key"))
    client = TestClient(app)
    monkeypatch.setattr("app.main.ModelGateway.infer", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("provider must not be called")))
    response = client.post("/v1/decisions", json={"tenant_id": "synthetic-tenant", "patient_id": "synthetic-patient", "question": "Which queue should receive this intake?", "permitted_options": ["routine", "review"], "synthetic": True})
    assert response.status_code == 200
    assert response.json()["abstained"] is True


def test_raw_model_confidence_is_not_exposed_as_probability():
    from app.decision import DecisionRequest, EvidenceReference, validate_output

    request = DecisionRequest(tenant_id="synthetic-tenant", patient_id="synthetic-patient", question="Which queue should receive this intake?", permitted_options=["routine", "review"], evidence=[EvidenceReference(source_id="synthetic-1", source_type="workflow", recorded_at="2026-01-01T00:00:00Z")], synthetic=True)
    output = validate_output(DecisionModelOutput(selected_option="routine", rationale="Supported fixture.", abstained=False, confidence=0.99), request)
    assert output.selected_option == "routine"
    assert output.confidence is None


def test_gateway_auth_is_required_and_scoped():
    settings = Settings(require_gateway_auth=True, service_token_secret="test-secret")
    client = TestClient(create_app(settings))
    payload = {"tenant_id": "synthetic-tenant", "patient_id": "synthetic-patient", "synthetic": True}
    assert client.post("/v1/snapshots", json=payload).status_code == 401
    token = make_test_token("test-secret", issuer="wyshcare", audience="wysh-ai", tenant_id="synthetic-tenant", patient_ids=["synthetic-patient"], scopes=["snapshot:write"])
    assert client.post("/v1/snapshots", json=payload, headers={"Authorization": f"Bearer {token}"}).status_code == 200
    wrong_tenant = make_test_token("test-secret", issuer="wyshcare", audience="wysh-ai", tenant_id="other-tenant", patient_ids=["synthetic-patient"], scopes=["snapshot:write"])
    assert client.post("/v1/snapshots", json=payload, headers={"Authorization": f"Bearer {wrong_tenant}"}).status_code == 401


def test_gateway_auth_rejects_expired_token():
    settings = Settings(require_gateway_auth=True, service_token_secret="test-secret")
    client = TestClient(create_app(settings))
    token = make_test_token("test-secret", issuer="wyshcare", audience="wysh-ai", tenant_id="synthetic-tenant", patient_ids=["synthetic-patient"], scopes=["snapshot:write"], ttl_seconds=-1)
    response = client.post("/v1/snapshots", json={"tenant_id": "synthetic-tenant", "patient_id": "synthetic-patient", "synthetic": True}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_rs256_jwks_gateway_verification(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private_key.private_numbers().public_numbers
    encode_bytes = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=").decode()
    jwks = {"keys": [{"kty": "RSA", "kid": "test-key", "use": "sig", "alg": "RS256", "n": encode_bytes(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")), "e": encode_bytes(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big"))}]}
    encode_json = lambda value: encode_bytes(json.dumps(value, separators=(",", ":")).encode())
    header = encode_json({"alg": "RS256", "typ": "JWT", "kid": "test-key"})
    now = int(time.time())
    payload = encode_json({"iss": "wyshcare", "aud": "wysh-ai", "sub": "jwks-gateway", "iat": now, "exp": now + 300, "tenant_id": "synthetic-tenant", "patient_ids": ["synthetic-patient"], "scope": ["snapshot:write"]})
    signing_input = f"{header}.{payload}".encode()
    signature = encode_bytes(private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256()))
    token = f"{header}.{payload}.{signature}"

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(jwks).encode()

    monkeypatch.setattr("app.auth.urlopen", lambda *args, **kwargs: FakeResponse())
    settings = Settings(service_token_algorithm="RS256", service_token_jwks_url="https://issuer.test/jwks", service_token_jwks_cache_ttl_seconds=60)
    principal = verify_bearer_token(f"Bearer {token}", settings, tenant_id="synthetic-tenant", patient_id="synthetic-patient", required_scope="snapshot:write")
    assert principal.subject == "jwks-gateway"


def test_decision_policy_rejects_diagnostic_scope():
    client = TestClient(create_app(Settings()))
    response = client.post(
        "/v1/decisions",
        json={"tenant_id": "synthetic-tenant", "patient_id": "synthetic-patient", "question": "What is the diagnosis?", "permitted_options": ["a", "b"], "synthetic": True},
    )
    assert response.status_code == 403


def test_provider_schema_validation_and_telemetry(monkeypatch):
    monkeypatch.setattr(
        "app.providers._json_request",
        lambda *args, **kwargs: (200, {"candidates": [{"content": {"parts": [{"text": '{"selected_option":"routine","rationale":"Enough","abstained":false,"confidence":0.8}'}]}}], "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 4}}),
    )
    settings = Settings(gemini_api_key="redacted-test-key", inference_enabled=True)
    output, telemetry = GeminiProvider(settings).infer("synthetic", DecisionModelOutput)
    assert output.selected_option == "routine"
    assert telemetry.schema_validated is True
    assert telemetry.prompt_tokens == 3


def test_gemini_key_is_sent_in_header_not_url(monkeypatch):
    captured = {}

    def fake_request(url, payload, headers, timeout_ms):
        captured.update({"url": url, "headers": headers})
        return 200, {"candidates": [{"content": {"parts": [{"text": '{"selected_option":"routine","rationale":"Enough","abstained":false}'}]}}]}

    monkeypatch.setattr("app.providers._json_request", fake_request)
    GeminiProvider(Settings(gemini_api_key="synthetic-only")).infer("synthetic", DecisionModelOutput)
    assert "synthetic-only" not in captured["url"]
    assert captured["headers"]["x-goog-api-key"] == "synthetic-only"


def test_cloud_and_openai_compatible_payloads_have_bounded_output_tokens(monkeypatch):
    payloads = []

    def fake_request(url, payload, headers, timeout_ms):
        payloads.append(payload)
        if "generateContent" in url:
            return 200, {"candidates": [{"content": {"parts": [{"text": '{"selected_option":"routine","rationale":"Enough","abstained":false}'}]}}]}
        return 200, {"choices": [{"message": {"content": '{"selected_option":"routine","rationale":"Enough","abstained":false}'}}]}

    monkeypatch.setattr("app.providers._json_request", fake_request)
    GeminiProvider(Settings(gemini_api_key="synthetic-only")).infer("synthetic", DecisionModelOutput)
    OpenAICompatibleProvider(Settings(openai_compatible_base_url="http://local.test", openai_compatible_model="synthetic-model")).infer("synthetic", DecisionModelOutput)
    assert payloads[0]["generationConfig"]["maxOutputTokens"] == 512
    assert payloads[1]["max_tokens"] == 512


def test_provider_missing_credentials_is_classified():
    with pytest.raises(ProviderError, match="invalid_credentials"):
        GeminiProvider(Settings()).infer("synthetic", DecisionModelOutput)


def test_provider_inference_timeout_is_bounded_and_classified(monkeypatch):
    calls = {"count": 0}

    def timeout(*args, **kwargs):
        calls["count"] += 1
        raise ProviderError("http", "timeout", "request timed out")

    monkeypatch.setattr("app.providers._json_request", timeout)
    settings = Settings(gemini_api_key="synthetic-only", provider_max_retries=1)
    with pytest.raises(ProviderError, match="timeout"):
        GeminiProvider(settings).infer("synthetic", DecisionModelOutput)
    assert calls["count"] == 2


def test_provider_telemetry_records_adapter_retry_count(monkeypatch):
    calls = {"count": 0}

    def flaky_request(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise ProviderError("http", "timeout", "synthetic timeout")
        return 200, {"candidates": [{"content": {"parts": [{"text": '{"selected_option":"routine","rationale":"Synthetic response.","abstained":false}' }]}}]}

    monkeypatch.setattr("app.providers._json_request", flaky_request)
    output, telemetry = GeminiProvider(Settings(gemini_api_key="synthetic-only", provider_max_retries=1)).infer("synthetic", DecisionModelOutput)
    assert output.selected_option == "routine"
    assert telemetry.retry_count == 1


def test_provider_rejects_oversized_request_before_network_call():
    settings = Settings(gemini_api_key="synthetic-only", provider_max_retries=0)
    with pytest.raises(ProviderError, match="request_too_large"):
        GeminiProvider(settings).infer("x" * 100_000, DecisionModelOutput)


def test_openai_compatible_provider_parses_structured_output(monkeypatch):
    monkeypatch.setattr(
        "app.providers._json_request",
        lambda *args, **kwargs: (200, {"choices": [{"message": {"content": '{"selected_option":"review","rationale":"Enough","abstained":false,"confidence":0.7}'}}], "usage": {"prompt_tokens": 5, "completion_tokens": 6}}),
    )
    settings = Settings(openai_compatible_base_url="http://local.test", openai_compatible_model="med-model")
    output, telemetry = OpenAICompatibleProvider(settings).infer("synthetic", DecisionModelOutput)
    assert output.selected_option == "review"
    assert telemetry.provider == "openai-compatible"
    assert telemetry.completion_tokens == 6


def test_auto_gateway_does_not_fallback_to_cloud_by_default():
    settings = Settings(model_routing_order=("gemini",), allow_cloud_fallback=False, inference_enabled=True)
    with pytest.raises(ProviderError, match="all_providers_failed"):
        ModelGateway(settings).infer("auto", "synthetic", DecisionModelOutput)


def test_gateway_requires_explicit_model_enablement(monkeypatch):
    settings = Settings(gemini_api_key="test-key", enabled_model_ids=frozenset(), inference_enabled=True)
    with pytest.raises(ProviderError, match="model_not_enabled"):
        ModelGateway(settings).infer("gemini", "synthetic", DecisionModelOutput)


def test_gateway_requires_manifest_enablement_in_addition_to_runtime_allowlist():
    settings = Settings(gemini_api_key="test-key", enabled_model_ids=frozenset({"gemini-2.5-flash"}), inference_enabled=True)
    with pytest.raises(ProviderError, match="model_not_enabled"):
        ModelGateway(settings).infer("gemini", "synthetic", DecisionModelOutput)


def test_synthetic_evaluation_enforces_abstention_and_option_validity():
    def predictor(case):
        if case.expected_option is None:
            return DecisionModelOutput(selected_option=None, rationale="Not enough evidence.", abstained=True)
        return DecisionModelOutput(selected_option=case.expected_option, rationale="Fixture.", abstained=False)

    results = evaluate(DEFAULT_CASES, predictor)
    assert len(results) == 3
    assert all(item.passed for item in results)


def test_env_bridge_is_allowlisted_and_health_redacts_secrets(tmp_path, monkeypatch):
    env_file = tmp_path / "wyshcare.env"
    env_file.write_text("GEMINI_API_KEY=secret-value\nDATABASE_URL=postgres://should-not-load\n", encoding="utf-8")
    settings = Settings.from_sources(str(env_file))
    assert settings.gemini_api_key == "secret-value"
    assert not hasattr(settings, "database_url")
    client = TestClient(create_app(settings))
    health = client.get("/health").json()
    assert "secret-value" not in json.dumps(health)
    assert health["providers"]["gemini_configured"] is True


def test_health_does_not_disclose_provider_endpoint_topology():
    client = TestClient(create_app(Settings(medgemma_base_url="http://internal-medgemma.example:11434")))
    body = json.dumps(client.get("/health").json())
    assert "internal-medgemma.example" not in body
    assert "medgemma_endpoint_configured" in body


def test_medgemma_readiness_and_timeout_are_fail_closed(monkeypatch):
    monkeypatch.setattr("app.providers.urllib.request.urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError()))
    assert MedGemmaProvider(Settings()).ready() is False


def test_medgemma_readiness_requires_the_configured_model(monkeypatch):
    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit=None):
            return json.dumps({"models": [{"name": "medgemma:latest"}]}).encode()

    monkeypatch.setattr("app.providers.urllib.request.urlopen", lambda *args, **kwargs: FakeResponse())
    assert MedGemmaProvider(Settings(medgemma_model="medgemma:latest")).ready() is True
    assert MedGemmaProvider(Settings(medgemma_model="medgemma:4b")).ready() is False


def test_openai_compatible_readiness_requires_the_configured_model(monkeypatch):
    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit=None):
            return json.dumps({"data": [{"id": "available-model"}]}).encode()

    monkeypatch.setattr("app.providers.urllib.request.urlopen", lambda *args, **kwargs: FakeResponse())
    assert OpenAICompatibleProvider(Settings(openai_compatible_base_url="http://local.test", openai_compatible_model="available-model")).ready() is True
    assert OpenAICompatibleProvider(Settings(openai_compatible_base_url="http://local.test", openai_compatible_model="missing-model")).ready() is False


def test_trion_contract_headers_and_response(monkeypatch):
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit=None):
            return json.dumps({"schemaVersion": 1, "documentId": "synthetic-doc", "resources": [], "generatedBy": "TRION"}).encode()

    def fake_urlopen(request, timeout):
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.trion.urllib.request.urlopen", fake_urlopen)
    settings = Settings(trion_enabled=True, trion_base_url="http://trion.test", trion_api_key="test-only")
    result = TrionClient(settings).execute({"schemaVersion": 1}, correlation_id="corr-1", idempotency_key="idem-1")
    assert result.status == "success"
    assert captured["headers"]["X-correlation-id"] == "corr-1"
    assert captured["headers"]["Idempotency-key"] == "idem-1"


def test_trion_disabled_without_endpoint():
    with pytest.raises(TrionError, match="disabled"):
        TrionClient(Settings()).execute({})


def test_trion_rejects_oversized_request_before_network_call():
    settings = Settings(trion_enabled=True, trion_base_url="http://trion.test", trion_api_key="test-only")
    with pytest.raises(TrionError, match="bounded payload limit"):
        TrionClient(settings).execute({"facts": "x" * 100_000})


def test_trion_rejects_invalid_endpoint_configuration():
    settings = Settings(trion_enabled=True, trion_base_url="https://user:secret@trion.test", trion_api_key="test-only")
    with pytest.raises(TrionError, match="configuration is invalid"):
        TrionClient(settings).execute({"schemaVersion": 1})


def test_trion_route_fails_closed_when_disabled():
    client = TestClient(create_app(Settings()))
    response = client.post("/v1/trion/fhir-draft", json={"tenant_id": "synthetic-tenant", "patient_id": "synthetic-patient", "document_id": "synthetic-doc", "synthetic": True, "facts": [{"statement": "Synthetic fact", "evidence": [{"source_id": "synthetic-1", "source_type": "observation", "recorded_at": "2026-01-01T00:00:00Z"}]}]})
    assert response.status_code == 503


def test_trion_route_validates_typed_contract_and_propagates_headers(monkeypatch):
    settings = Settings(trion_enabled=True, trion_base_url="http://trion.test", trion_api_key="test-only")
    captured = {}

    def fake_execute(self, request_payload, *, correlation_id=None, idempotency_key=None):
        captured.update({"payload": request_payload, "correlation_id": correlation_id, "idempotency_key": idempotency_key})
        return TrionResult("success", correlation_id, idempotency_key or "generated", {"schemaVersion": 1, "documentId": "synthetic-doc", "resources": [], "generatedBy": "TRION", "model": "trion-test"})

    monkeypatch.setattr("app.main.TrionClient.execute", fake_execute)
    app = create_app(settings)
    response = TestClient(app).post("/v1/trion/fhir-draft", headers={"X-Correlation-Id": "corr-trion", "Idempotency-Key": "idem-trion"}, json={"tenant_id": "synthetic-tenant", "patient_id": "synthetic-patient", "document_id": "synthetic-doc", "synthetic": True, "facts": [{"statement": "Synthetic fact", "evidence": [{"source_id": "synthetic-1", "source_type": "observation", "recorded_at": "2026-01-01T00:00:00Z"}]}]})
    assert response.status_code == 200
    assert response.json()["generatedBy"] == "TRION"
    assert captured["correlation_id"] == "corr-trion"
    assert captured["idempotency_key"] == "idem-trion"


def test_trion_authenticated_boundary_binds_clinical_context(monkeypatch):
    secret = "trion-auth-secret"
    settings = Settings(trion_enabled=True, trion_base_url="http://trion.test", trion_api_key="test-only", require_gateway_auth=True, service_token_secret=secret)

    def fake_execute(self, request_payload, *, correlation_id=None, idempotency_key=None):
        return TrionResult("success", correlation_id, idempotency_key or "generated", {"schemaVersion": 1, "documentId": "synthetic-doc", "resources": [], "generatedBy": "TRION", "model": "trion-test"})

    monkeypatch.setattr("app.main.TrionClient.execute", fake_execute)
    token = make_test_token(secret, issuer="wyshcare", audience="wysh-ai", tenant_id="synthetic-tenant", patient_ids=["synthetic-patient"], scopes=["trion:fhir-draft"], roles=["clinician"], subject="synthetic-clinician", purpose_of_use="synthetic-evaluation", consent_id="synthetic-consent")
    payload = {"tenant_id": "synthetic-tenant", "patient_id": "synthetic-patient", "document_id": "synthetic-doc", "practitioner_subject": "synthetic-clinician", "purpose_of_use": "synthetic-evaluation", "consent_id": "synthetic-consent", "synthetic": True, "facts": [{"statement": "Synthetic fact", "evidence": [{"source_id": "synthetic-1", "source_type": "observation", "recorded_at": "2026-01-01T00:00:00Z"}]}]}
    client = TestClient(create_app(settings))
    allowed = client.post("/v1/trion/fhir-draft", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert allowed.status_code == 200
    denied = client.post("/v1/trion/fhir-draft", headers={"Authorization": f"Bearer {token}"}, json={**payload, "consent_id": "different-consent"})
    assert denied.status_code == 403


def test_trion_route_replays_and_rejects_conflicting_idempotency_content(monkeypatch):
    settings = Settings(trion_enabled=True, trion_base_url="http://trion.test", trion_api_key="test-only")
    calls = {"count": 0}

    def fake_execute(self, request_payload, *, correlation_id=None, idempotency_key=None):
        calls["count"] += 1
        return TrionResult("success", correlation_id, idempotency_key or "generated", {"schemaVersion": 1, "documentId": "synthetic-doc", "resources": [], "generatedBy": "TRION", "model": "trion-test"})

    monkeypatch.setattr("app.main.TrionClient.execute", fake_execute)
    client = TestClient(create_app(settings))
    payload = {"tenant_id": "synthetic-tenant", "patient_id": "synthetic-patient", "document_id": "synthetic-doc", "synthetic": True, "facts": [{"statement": "Synthetic fact", "evidence": [{"source_id": "synthetic-1", "source_type": "observation", "recorded_at": "2026-01-01T00:00:00Z"}]}]}
    first = client.post("/v1/trion/fhir-draft", headers={"Idempotency-Key": "trion-idem-1"}, json=payload)
    replay = client.post("/v1/trion/fhir-draft", headers={"Idempotency-Key": "trion-idem-1"}, json=payload)
    conflict = client.post("/v1/trion/fhir-draft", headers={"Idempotency-Key": "trion-idem-1"}, json={**payload, "document_id": "different-doc"})
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    assert conflict.status_code == 409
    assert calls["count"] == 1


def test_metrics_are_low_cardinality_and_redacted():
    client = TestClient(create_app(Settings()))
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert 'event="http_requests"' in response.text
    assert "synthetic-" not in response.text
    assert "Authorization" not in response.text


def test_metrics_can_record_success_without_sensitive_labels():
    client = TestClient(create_app(Settings()))
    app = client.app
    app.state.metrics.inc("inference_successes")
    app.state.metrics.inc("inference_schema_validated")
    response = client.get("/metrics")
    assert 'event="inference_successes"' in response.text
    assert 'event="inference_schema_validated"' in response.text
    assert "medgemma" not in response.text
