from __future__ import annotations

import os
import re
import json
from dataclasses import asdict
from hashlib import sha256
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from .audit import InMemoryAuditSink, new_event
from .auth import AuthError, GatewayPrincipal, verify_bearer_token
from .capabilities import load_capability_catalog, public_capabilities
from .config import Settings
from .decision import DecisionModelOutput, DecisionRequest, DecisionResponse, DecisionProvenance, DecisionRouteAttempt, DecisionTelemetry, generated_at, input_hash, policy_check, validate_output
from .gateway import ModelGateway
from .knowledge import GroundingRequest, GroundingResponse, ground
from .imaging import ImagingAnalysisRequest, ImagingAnalysisResponse, ImagingProvenance, compose_report, compose_segmentation_job, assess_quality, imaging_input_hash, plan_workflow
from .disease_intelligence import MonitoringRequest, MonitoringResponse, describe_monitoring, get_definition, get_workflow, load_disease_catalog, load_phase1_workflows
from .clinical_rules import RuleEvaluationResponse, evaluate_rules, load_rules
from .fhir_adapter import FHIRMonitoringRequest, bundle_to_monitoring
from .metrics import Metrics
from .providers import MedGemmaProvider, OpenAICompatibleProvider, ProviderError
from .registry import load_registry, public_registry
from .schemas import SnapshotRequest, SnapshotResponse
from .trion import TrionClient, TrionError
from .trion_contract import TrionFhirDraftRequest, TrionFhirDraftResponse
from .clinical_engine import ClinicalAssessmentRequest, ClinicalAssessmentResponse, assess
from .reuse_accelerator import (
    CdsPathwayRequest,
    CdsPathwayResponse,
    CqlExecutionRequest,
    CqlExecutionResponse,
    NocturneIngestRequest,
    NocturneIngestResponse,
    UnifiedAssessmentRequest,
    UnifiedAssessmentResponse,
    evaluate_cds_pathway,
    execute_cql_contract,
    ingest_nocturne,
    unified_assessment,
)
from .standards_cql import StandardsCqlRequest, StandardsCqlResponse, execute_fhir_elm_subset
from .upstream_cql_runtime import UpstreamCqlRuntimeResponse, execute_pinned_runtime
from .terminology import TerminologyValidationRequest, TerminologyValidationResponse, validate_code
from .console_contracts import EvaluationStatus, SyntheticPatientCase, SyntheticPatientIndex, SyntheticPatientSummary, load_evaluation_status, load_synthetic_cases
from .review_contracts import ClinicalReviewCreateRequest, ClinicalReviewDecisionRequest, ClinicalReviewEventResponse, ClinicalReviewResponse
from .review_store import ClinicalReview, ReviewConflict, ReviewNotFound, ReviewStore
from .replay_cache import ReplayCache
from .verified_calculations import CalculationRequest, VerifiedCalculationResponse, calculate
from .disease_specific_intelligence import DiseaseSpecificRequest, DiseaseSpecificResponse, evaluate as evaluate_disease_specific
from .approved_clinical_rules import ClinicalRuleResponse, evaluate_diabetes_hypoglycemia, evidence_registry_path
from .rule_governance_contracts import RuleCreateRequest, RuleEventResponse, RuleGovernanceResponse, RuleTransitionRequest
from .rule_governance_store import GovernedRule, RuleConflict, RuleGovernanceStore, RuleNotFound, RuleValidationError
from .clinical_orchestration import ClinicalWorkflowRequest, ClinicalWorkflowResponse, execute_workflow
from .workbench import WorkbenchRequest, WorkbenchResponse, assemble_workbench, validate_workbench_access
from .bridge_contracts import WyshCareAIBridgeRequest, WyshAIBridgeResult
from .bridge_service import execute_synthetic_bridge


_CORRELATION_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _safe_correlation_id(value: str | None) -> str:
    return value if value and _CORRELATION_ID_RE.fullmatch(value) else str(uuid4())


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_sources(os.getenv("WYSH_AI_ENV_FILE"))
    explicit_settings = settings is not None

    def current_config() -> Settings:
        return config if explicit_settings else Settings.from_sources(os.getenv("WYSH_AI_ENV_FILE"))

    def authorize(active: Settings, authorization: str | None, tenant_id: str, patient_id: str | None, scope: str) -> None:
        if not (active.require_gateway_auth or active.environment != "development"):
            return
        try:
            verify_bearer_token(authorization, active, tenant_id=tenant_id, patient_id=patient_id, required_scope=scope)
        except AuthError as exc:  # noqa
            raise HTTPException(status_code=401, detail="gateway authorization failed") from None

    def authorize_wyshcare_bridge(active: Settings, authorization: str | None, req: WyshCareAIBridgeRequest) -> GatewayPrincipal | None:
        """Verify the bridge token against the request's purpose and actor.

        Generic route authorization is insufficient here: the bridge request
        carries purpose, consent, delegation and practitioner identity that
        must agree with the signed WyshCare context.
        """
        if not (active.require_gateway_auth or active.environment != "development"):
            return None
        try:
            principal = verify_bearer_token(
                authorization,
                active,
                tenant_id=req.tenant_id,
                patient_id=req.patient_id,
                required_scope="clinical-workflow:execute",
            )
        except AuthError:
            raise HTTPException(status_code=401, detail="gateway authorization failed") from None
        if "clinician" not in principal.roles and "clinical-reviewer" not in principal.roles:
            raise HTTPException(status_code=403, detail="clinical workflow role required")
        if not req.practitioner_subject or principal.subject != req.practitioner_subject:
            raise HTTPException(status_code=403, detail="practitioner scope denied")
        if principal.purpose_of_use != req.purpose_of_use or principal.consent_id != req.consent_id:
            raise HTTPException(status_code=403, detail="purpose or consent boundary denied")
        if principal.delegated_by != req.delegated_by:
            raise HTTPException(status_code=403, detail="delegated access boundary denied")
        return principal

    def authorize_trion_boundary(active: Settings, authorization: str | None, req: TrionFhirDraftRequest) -> GatewayPrincipal | None:
        """Bind authenticated TRION drafts to the same clinical context."""
        if not (active.require_gateway_auth or active.environment != "development"):
            return None
        try:
            principal = verify_bearer_token(
                authorization,
                active,
                tenant_id=req.tenant_id,
                patient_id=req.patient_id,
                required_scope="trion:fhir-draft",
            )
        except AuthError:
            raise HTTPException(status_code=401, detail="gateway authorization failed") from None
        if "clinician" not in principal.roles and "clinical-reviewer" not in principal.roles:
            raise HTTPException(status_code=403, detail="clinical workflow role required")
        if not req.practitioner_subject or principal.subject != req.practitioner_subject:
            raise HTTPException(status_code=403, detail="practitioner scope denied")
        if not req.purpose_of_use or principal.purpose_of_use != req.purpose_of_use or not req.consent_id or principal.consent_id != req.consent_id:
            raise HTTPException(status_code=403, detail="purpose or consent boundary denied")
        if principal.delegated_by != req.delegated_by:
            raise HTTPException(status_code=403, detail="delegated access boundary denied")
        return principal

    application = FastAPI(title="wysh.AI WMI-1", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Correlation-Id", "Idempotency-Key"],
    )
    application.state.audit_sink = InMemoryAuditSink()
    application.state.model_registry = load_registry()
    application.state.capability_catalog = load_capability_catalog()
    application.state.metrics = Metrics()
    application.state.review_store = ReviewStore()
    application.state.rule_governance_store = RuleGovernanceStore()
    application.state.bridge_requests = ReplayCache()
    application.state.trion_requests = ReplayCache()
    application.state.decision_requests = ReplayCache()

    def authorize_clinical_review(active: Settings, authorization: str | None, tenant_id: str, patient_id: str, scope: str) -> GatewayPrincipal:
        try:
            principal = verify_bearer_token(authorization, active, tenant_id=tenant_id, patient_id=patient_id, required_scope=scope)
        except AuthError:
            raise HTTPException(status_code=401, detail="clinical review authorization failed") from None
        if "clinician" not in principal.roles:
            raise HTTPException(status_code=403, detail="clinician role required")
        return principal

    def authorize_workbench(active: Settings, authorization: str | None, req: WorkbenchRequest) -> GatewayPrincipal:
        try:
            principal = verify_bearer_token(authorization, active, tenant_id=req.tenant_id, patient_id=req.patient_id, required_scope="clinical-workbench:read")
            validate_workbench_access(principal=principal, access=req.access, tenant_id=req.tenant_id, patient_id=req.patient_id)
        except AuthError:
            raise HTTPException(status_code=401, detail="clinical workbench authorization failed") from None
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None
        return principal

    def review_response(review: ClinicalReview) -> ClinicalReviewResponse:
        return ClinicalReviewResponse(
            review_id=review.review_id, tenant_id=review.tenant_id, patient_id=review.patient_id,
            disease_id=review.disease_id, assessment_id=review.assessment_id, assessment_input_hash=review.assessment_input_hash,
            state=review.state, version=review.version, created_at=review.created_at, updated_at=review.updated_at,
            created_by=review.created_by, latest_action=review.latest_action,
            events=[ClinicalReviewEventResponse(**event.__dict__) for event in review.events],
        )

    def authorize_rule_governance(active: Settings, authorization: str | None, tenant_id: str, scope: str, roles: set[str]) -> GatewayPrincipal:
        try:
            principal = verify_bearer_token(authorization, active, tenant_id=tenant_id, patient_id=None, required_scope=scope)
        except AuthError:
            raise HTTPException(status_code=401, detail="rule governance authorization failed") from None
        if not principal.roles.intersection(roles):
            raise HTTPException(status_code=403, detail="required rule governance role missing")
        return principal

    def governed_rule_response(rule: GovernedRule) -> RuleGovernanceResponse:
        return RuleGovernanceResponse(
            rule_id=rule.rule_id, tenant_id=rule.tenant_id, rule_version=rule.rule_version,
            disease_id=rule.disease_id, evidence_id=rule.evidence_id, intended_use=rule.intended_use,
            status=rule.status, version=rule.version, revision_hash=rule.revision_hash,
            created_at=rule.created_at, updated_at=rule.updated_at, expires_at=rule.expires_at,
            created_by=rule.created_by, approved_by=rule.approved_by, approved_at=rule.approved_at,
            events=[RuleEventResponse(**event.__dict__) for event in rule.events],
        )

    @application.middleware("http")
    async def correlation_id_middleware(request, call_next):
        correlation_id = _safe_correlation_id(request.headers.get("X-Correlation-Id"))
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        application.state.metrics.inc("http_requests")
        application.state.metrics.inc(f"http_status_{response.status_code}")
        response.headers["X-Correlation-Id"] = correlation_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @application.get("/metrics", response_class=PlainTextResponse)

    def metrics():  # noqa
        return application.state.metrics.render()

    @application.get("/health")

    def health():  # noqa
        active = current_config()
        return {"status": "ok", "clinical_use_authorized": False, "providers": active.provider_public_status(), "model_registry": public_registry(application.state.model_registry, active)}

    @application.get("/v1/models")

    def models():  # noqa
        return public_registry(application.state.model_registry, current_config())

    @application.get("/v1/models/readiness")

    def model_readiness(probe_local: bool = False):  # noqa
        """Expose redacted model readiness without contacting cloud providers by default."""
        active = current_config()
        registry = application.state.model_registry

        def entry(model_id: str, provider: str, configured: bool, runtime_enabled: bool, ready: bool | None, reason: str) -> dict[str, object]:
            return {
                "model_id": model_id,
                "provider": provider,
                "configured": configured,
                "runtime_enabled": runtime_enabled,
                "ready": ready,
                "reason": reason,
                "clinical_use_authorized": False,
            }

        medgemma_manifest = next((item for item in registry.models if item.id == active.medgemma_model), None)
        medgemma_enabled = bool(medgemma_manifest and medgemma_manifest.enabled and active.medgemma_model in active.enabled_model_ids)
        medgemma_ready: bool | None = None
        medgemma_reason = "local probe not requested"
        if probe_local and medgemma_enabled:
            medgemma_ready = MedGemmaProvider(active).ready()
            medgemma_reason = "ollama model inventory matched" if medgemma_ready else "ollama model unavailable"
        elif not medgemma_enabled:
            medgemma_reason = "manifest or runtime allowlist disabled"

        openai_configured = bool(active.openai_compatible_base_url and active.openai_compatible_model)
        openai_enabled = bool(openai_configured and active.openai_compatible_model in active.enabled_model_ids)
        openai_ready: bool | None = None
        openai_reason = "local-compatible probe not requested"
        if probe_local and openai_enabled:
            openai_ready = OpenAICompatibleProvider(active).ready()
            openai_reason = "compatible endpoint responded" if openai_ready else "compatible endpoint unavailable"
        elif not openai_enabled:
            openai_reason = "endpoint configuration or runtime allowlist disabled"

        return {
            "probe_local": probe_local,
            "providers": [
                entry(active.medgemma_model, "medgemma", bool(active.medgemma_base_url), medgemma_enabled, medgemma_ready, medgemma_reason),
                entry(active.gemini_model, "gemini", bool(active.gemini_api_key), active.gemini_model in active.enabled_model_ids, None, "cloud readiness is credential-gated and not probed by this endpoint"),
                entry(active.openai_compatible_model or "unconfigured", "openai-compatible", openai_configured, openai_enabled, openai_ready, openai_reason),
                entry(active.trion_model or "unconfigured", "trion", bool(active.trion_enabled and active.trion_base_url and active.trion_api_key), False, None, "TRION readiness requires an explicit contract-gated request"),
            ],
            "clinical_use_authorized": False,
        }

    @application.get("/v1/capabilities")

    def capabilities():  # noqa
        return public_capabilities(application.state.capability_catalog)

    @application.get("/v1/clinical-rule-governance/status")

    def clinical_rule_governance_status():  # noqa
        registry = json.loads(evidence_registry_path().read_text(encoding="utf-8"))
        entry = registry["entries"][0]
        return {
            "rule_id": "diabetes.hypoglycemia-observation",
            "rule_version": "r6b-diabetes-hypoglycemia-v1",
            "evidence_id": entry["evidence_id"],
            "registry_approval_status": entry["approval_status"],
            "lifecycle_available": True,
            "clinical_use_authorized": False,
            "clinical_approval_claimed": False,
            "synthetic_only": True,
        }

    @application.get("/v1/disease-intelligence/catalog")

    def disease_catalog():  # noqa
        catalog = load_disease_catalog()
        workflows = load_phase1_workflows()
        return {"catalog": catalog.model_dump(mode="json"), "phase1_workflows": workflows.model_dump(mode="json")}

    @application.get("/v1/console/synthetic-patients", response_model=SyntheticPatientIndex)

    def console_synthetic_patients():  # noqa
        return SyntheticPatientIndex(patients=[SyntheticPatientSummary(case_id=item.case_id, disease_id=item.disease_id, measurement_count=item.measurement_count, expected_engineering_status=item.expected_engineering_status) for item in load_synthetic_cases()])

    @application.get("/v1/console/synthetic-patients/{case_id}", response_model=SyntheticPatientCase)

    def console_synthetic_patient(case_id: str):  # noqa
        match = next((item for item in load_synthetic_cases() if item.case_id == case_id), None)
        if match is None:
            raise HTTPException(status_code=404, detail="synthetic patient case not found")
        return match

    @application.get("/v1/console/evaluation-status", response_model=EvaluationStatus)

    def console_evaluation_status():  # noqa
        return load_evaluation_status()

    @application.post("/v1/integration/wyshcare/clinical-draft", response_model=WyshAIBridgeResult)

    def wyshcare_clinical_draft(request: Request, req: WyshCareAIBridgeRequest, authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):  # noqa
        active = current_config()
        if active.environment != "development":
            raise HTTPException(status_code=503, detail="WyshCare bridge disabled outside isolated development")
        authorize_wyshcare_bridge(active, authorization, req)
        result = execute_synthetic_bridge(req)
        replay_key = idempotency_key or req.request_id
        previous = application.state.bridge_requests.get(replay_key)
        if previous is not None:
            if previous.provenance_hash != result.provenance_hash:
                raise HTTPException(status_code=409, detail="bridge request identity already used for different content")
            application.state.metrics.inc("wyshcare_bridge_replay")
            return previous
        application.state.bridge_requests.put(replay_key, result)
        application.state.audit_sink.append(
            new_event(
                "wyshcare_bridge.abstained",
                request.state.correlation_id,
                req.tenant_id,
                req.practitioner_subject or "synthetic-bridge",
                result.status,
                input_hash=result.provenance_hash,
                policy_version="wyshcare-ai-bridge-v1",
            )
        )
        application.state.metrics.inc("wyshcare_bridge_abstained")
        return result

    @application.post("/v1/clinical-reviews", response_model=ClinicalReviewResponse, status_code=201)

    def create_clinical_review(request: Request, req: ClinicalReviewCreateRequest, authorization: str | None = Header(default=None)):  # noqa
        active = current_config()
        if active.environment != "development":
            raise HTTPException(status_code=503, detail="Clinical review disabled pending security and safety approval")
        principal = authorize_clinical_review(active, authorization, req.tenant_id, req.patient_id, "clinical-review:write")
        if not req.synthetic or not req.tenant_id.startswith("synthetic-") or not req.patient_id.startswith("synthetic-"):
            raise HTTPException(status_code=403, detail="Only synthetic clinical reviews are allowed")
        review = application.state.review_store.create(
            tenant_id=req.tenant_id, patient_id=req.patient_id, disease_id=req.disease_id,
            assessment_id=req.assessment_id, assessment_input_hash=req.assessment_input_hash, actor_subject=principal.subject,
        )
        application.state.audit_sink.append(new_event("clinical_review.created", request.state.correlation_id, req.tenant_id, principal.subject, "created", input_hash=req.assessment_input_hash, policy_version="r4a-review-v1"))
        application.state.metrics.inc("clinical_review_created")
        return review_response(review)

    @application.get("/v1/clinical-reviews/{review_id}", response_model=ClinicalReviewResponse)

    def get_clinical_review(review_id: str, tenant_id: str, patient_id: str, authorization: str | None = Header(default=None)):  # noqa
        active = current_config()
        if active.environment != "development":
            raise HTTPException(status_code=503, detail="Clinical review disabled pending security and safety approval")
        authorize_clinical_review(active, authorization, tenant_id, patient_id, "clinical-review:read")
        try:
            return review_response(application.state.review_store.get(review_id, tenant_id=tenant_id, patient_id=patient_id))
        except ReviewNotFound:
            raise HTTPException(status_code=404, detail="clinical review not found") from None

    @application.post("/v1/clinical-reviews/{review_id}/decision", response_model=ClinicalReviewResponse)

    def decide_clinical_review(review_id: str, request: Request, req: ClinicalReviewDecisionRequest, authorization: str | None = Header(default=None)):  # noqa
        active = current_config()
        if active.environment != "development":
            raise HTTPException(status_code=503, detail="Clinical review disabled pending security and safety approval")
        principal = authorize_clinical_review(active, authorization, req.tenant_id, req.patient_id, "clinical-review:write")
        if not req.synthetic or not req.tenant_id.startswith("synthetic-") or not req.patient_id.startswith("synthetic-"):
            raise HTTPException(status_code=403, detail="Only synthetic clinical reviews are allowed")
        try:
            review = application.state.review_store.decide(
                review_id=review_id, tenant_id=req.tenant_id, patient_id=req.patient_id,
                expected_version=req.expected_version, action=req.action, actor_subject=principal.subject, note=req.note,
            )
        except ReviewNotFound:
            raise HTTPException(status_code=404, detail="clinical review not found") from None
        except ReviewConflict:
            application.state.audit_sink.append(new_event("clinical_review.conflict", request.state.correlation_id, req.tenant_id, principal.subject, "conflict", policy_version="r4a-review-v1"))
            application.state.metrics.inc("clinical_review_conflicts")
            raise HTTPException(status_code=409, detail="review version conflict or terminal review state") from None
        event_type = {"approve": "clinical_review.approved", "reject": "clinical_review.rejected", "request_revision": "clinical_review.revision_requested"}[req.action]
        application.state.audit_sink.append(new_event(event_type, request.state.correlation_id, req.tenant_id, principal.subject, review.state.lower(), policy_version="r4a-review-v1"))
        application.state.metrics.inc(f"clinical_review_{req.action}")
        return review_response(review)

    @application.post("/v1/clinical-rule-governance/rules", response_model=RuleGovernanceResponse, status_code=201)

    def create_governed_rule(req: RuleCreateRequest, request: Request, authorization: str | None = Header(default=None)):  # noqa
        active = current_config()
        if active.environment != "development":
            raise HTTPException(status_code=503, detail="Rule governance disabled pending clinical governance approval")
        principal = authorize_rule_governance(active, authorization, req.tenant_id, "clinical-rule:write", {"rule-engineer", "clinical-governance"})
        try:
            result = application.state.rule_governance_store.create(tenant_id=req.tenant_id, rule_id=req.rule_id, rule_version=req.rule_version, disease_id=req.disease_id, evidence_id=req.evidence_id, intended_use=req.intended_use, revision_hash=req.revision_hash, expires_at=req.expires_at, actor_subject=principal.subject)
        except RuleConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        except RuleValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        application.state.audit_sink.append(new_event("clinical_rule.created", request.state.correlation_id, req.tenant_id, principal.subject, "DRAFT", policy_version=req.rule_version))
        return governed_rule_response(result)

    @application.get("/v1/clinical-rule-governance/rules/{rule_id}", response_model=RuleGovernanceResponse)

    def get_governed_rule(rule_id: str, tenant_id: str, authorization: str | None = Header(default=None)):  # noqa
        active = current_config()
        if active.environment != "development":
            raise HTTPException(status_code=503, detail="Rule governance disabled pending clinical governance approval")
        authorize_rule_governance(active, authorization, tenant_id, "clinical-rule:read", {"rule-engineer", "clinical-reviewer", "clinical-governance"})
        try:
            return governed_rule_response(application.state.rule_governance_store.get(tenant_id, rule_id))
        except RuleNotFound:
            raise HTTPException(status_code=404, detail="clinical rule not found") from None

    def transition_governed_rule(rule_id: str, action: str, req: RuleTransitionRequest, request: Request, authorization: str | None = Header(default=None)):
        active = current_config()
        if active.environment != "development":
            raise HTTPException(status_code=503, detail="Rule governance disabled pending clinical governance approval")
        required = {"submitted": ("clinical-rule:submit", {"rule-engineer", "clinical-governance"}), "approved": ("clinical-rule:approve", {"clinical-reviewer"}), "activated": ("clinical-rule:activate", {"clinical-governance"}), "revoked": ("clinical-rule:revoke", {"clinical-governance"}), "rejected": ("clinical-rule:reject", {"clinical-reviewer", "clinical-governance"})}[action]
        principal = authorize_rule_governance(active, authorization, req.tenant_id, required[0], required[1])
        try:
            result = application.state.rule_governance_store.transition(tenant_id=req.tenant_id, rule_id=rule_id, expected_version=req.expected_version, action=action, evidence_id=req.evidence_id, actor_subject=principal.subject, actor_role=next(iter(principal.roles.intersection(required[1]))), note=req.note)
        except RuleNotFound:
            raise HTTPException(status_code=404, detail="clinical rule not found") from None
        except RuleConflict as exc:
            application.state.audit_sink.append(new_event("clinical_rule.conflict", request.state.correlation_id, req.tenant_id, principal.subject, "conflict", policy_version="r6b-rule-governance-v1"))
            raise HTTPException(status_code=409, detail=str(exc)) from None
        except RuleValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        application.state.audit_sink.append(new_event(f"clinical_rule.{action}", request.state.correlation_id, req.tenant_id, principal.subject, result.status, policy_version="r6b-rule-governance-v1"))
        return governed_rule_response(result)

    @application.post("/v1/clinical-rule-governance/rules/{rule_id}/submit", response_model=RuleGovernanceResponse)

    def submit_governed_rule(rule_id: str, req: RuleTransitionRequest, request: Request, authorization: str | None = Header(default=None)):  # noqa
        return transition_governed_rule(rule_id, "submitted", req, request, authorization)

    @application.post("/v1/clinical-rule-governance/rules/{rule_id}/approve", response_model=RuleGovernanceResponse)

    def approve_governed_rule(rule_id: str, req: RuleTransitionRequest, request: Request, authorization: str | None = Header(default=None)):  # noqa
        return transition_governed_rule(rule_id, "approved", req, request, authorization)

    @application.post("/v1/clinical-rule-governance/rules/{rule_id}/activate", response_model=RuleGovernanceResponse)

    def activate_governed_rule(rule_id: str, req: RuleTransitionRequest, request: Request, authorization: str | None = Header(default=None)):  # noqa
        return transition_governed_rule(rule_id, "activated", req, request, authorization)

    @application.post("/v1/clinical-rule-governance/rules/{rule_id}/revoke", response_model=RuleGovernanceResponse)

    def revoke_governed_rule(rule_id: str, req: RuleTransitionRequest, request: Request, authorization: str | None = Header(default=None)):  # noqa
        return transition_governed_rule(rule_id, "revoked", req, request, authorization)

    @application.get("/v1/disease-intelligence/workflows/{disease_id}")

    def disease_workflow(disease_id: str):  # noqa
        try:
            definition = get_definition(disease_id)
            workflow = get_workflow(disease_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        return {"definition": definition.model_dump(mode="json"), "workflow": workflow.model_dump(mode="json"), "clinical_use_authorized": False}

    @application.post("/v1/disease-intelligence/monitor", response_model=MonitoringResponse)

    def disease_monitor(request: Request, req: MonitoringRequest, authorization: str | None = Header(default=None)):  # noqa
        active = current_config()
        if active.environment != "development":
            raise HTTPException(status_code=503, detail="Disease intelligence disabled pending security and safety approval")
        authorize(active, authorization, req.tenant_id, req.patient_id, "disease:monitor")
        if not req.synthetic or not req.tenant_id.startswith("synthetic-") or not req.patient_id.startswith("synthetic-"):
            raise HTTPException(status_code=403, detail="Only synthetic disease monitoring is allowed")
        try:
            get_definition(req.disease_id)
            workflow = get_workflow(req.disease_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        result = describe_monitoring(req, workflow)
        application.state.metrics.inc("disease_monitor_requests")
        application.state.audit_sink.append(new_event("disease.monitored", request.state.correlation_id, req.tenant_id, req.patient_id, "completed", policy_version=f"wdi-{workflow.workflow_version}", input_hash=result.input_hash))
        return result

    @application.post("/v1/disease-intelligence/rules/evaluate", response_model=RuleEvaluationResponse)

    def disease_rules(request: Request, req: MonitoringRequest, authorization: str | None = Header(default=None)):  # noqa
        active = current_config()
        if active.environment != "development":
            raise HTTPException(status_code=503, detail="Clinical rules disabled pending security and safety approval")
        authorize(active, authorization, req.tenant_id, req.patient_id, "disease:rules")
        if not req.synthetic or not req.tenant_id.startswith("synthetic-") or not req.patient_id.startswith("synthetic-"):
            raise HTTPException(status_code=403, detail="Only synthetic clinical-rule evaluation is allowed")
        if not any(rule.disease_id == req.disease_id for rule in load_rules().rules):
            raise HTTPException(status_code=422, detail="no deterministic rule pack is enabled for this disease")
        result = evaluate_rules(req)
        application.state.metrics.inc("disease_rule_evaluations")
        application.state.audit_sink.append(new_event("disease.rules_evaluated", request.state.correlation_id, req.tenant_id, req.patient_id, "completed", policy_version=result.ruleset_version, input_hash=result.input_hash))
        return result

    @application.post("/v1/disease-intelligence/fhir/monitor", response_model=MonitoringResponse)

    def fhir_disease_monitor(request: Request, req: FHIRMonitoringRequest, authorization: str | None = Header(default=None)):  # noqa
        active = current_config()
        if active.environment != "development":
            raise HTTPException(status_code=503, detail="FHIR disease monitoring disabled pending security and safety approval")
        authorize(active, authorization, req.tenant_id, req.patient_id, "disease:monitor")
        if not req.synthetic or not req.tenant_id.startswith("synthetic-") or not req.patient_id.startswith("synthetic-"):
            raise HTTPException(status_code=403, detail="Only synthetic FHIR monitoring is allowed")
        try:
            monitoring = bundle_to_monitoring(req)
            workflow = get_workflow(req.disease_id)
        except (ValueError, TypeError, KeyError):
            raise HTTPException(status_code=422, detail="FHIR Bundle contained no supported typed observations") from None
        result = describe_monitoring(monitoring, workflow)
        application.state.metrics.inc("disease_fhir_monitor_requests")
        application.state.audit_sink.append(new_event("disease.monitored", request.state.correlation_id, req.tenant_id, req.patient_id, "completed", policy_version=f"fhir-{workflow.workflow_version}", input_hash=result.input_hash))
        return result

    @application.post("/v1/disease-intelligence/clinical-assess", response_model=ClinicalAssessmentResponse)

    def clinical_assessment(request: Request, req: ClinicalAssessmentRequest, authorization: str | None = Header(default=None)):  # noqa
        active = current_config()
        if active.environment != "development":
            raise HTTPException(status_code=503, detail="Clinical assessment disabled pending security and safety approval")
        authorize(active, authorization, req.tenant_id, req.patient_id, "disease:assess")
        if not req.synthetic or not req.tenant_id.startswith("synthetic-") or not req.patient_id.startswith("synthetic-"):
            raise HTTPException(status_code=403, detail="Only synthetic clinical assessment is allowed")
        result = assess(req)
        application.state.metrics.inc("clinical_assessments")
        application.state.metrics.inc("clinical_assessment_reviews" if result.follow_up_status != "NO_GAP_DETECTED" else "clinical_assessment_clear")
        application.state.audit_sink.append(new_event("disease.assessed", request.state.correlation_id, req.tenant_id, req.patient_id, "review_required" if result.human_review_required else "completed", policy_version=result.provenance.engine_version, input_hash=result.provenance.input_hash))
        return result

    @application.post("/v1/disease-intelligence/verified-calculations", response_model=VerifiedCalculationResponse)

    def verified_calculations(request: Request, req: CalculationRequest, authorization: str | None = Header(default=None)):  # noqa
        active = current_config()
        if active.environment != "development":
            raise HTTPException(status_code=503, detail="Verified calculations disabled pending security and safety approval")
        authorize(active, authorization, req.tenant_id, req.patient_id, "disease:calculate")
        if not req.synthetic or not req.tenant_id.startswith("synthetic-") or not req.patient_id.startswith("synthetic-"):
            raise HTTPException(status_code=403, detail="Only synthetic verified calculations are allowed")
        if req.disease_id not in {"diabetes", "hypertension", "chronic-kidney-disease"}:
            raise HTTPException(status_code=422, detail="R4B calculation pack is not enabled for this disease")
        result = calculate(req)
        application.state.metrics.inc("verified_calculation_requests")
        application.state.audit_sink.append(new_event("disease.assessed", request.state.correlation_id, req.tenant_id, req.patient_id, "abstained" if result.abstained else "completed", policy_version=result.provenance.calculation_version, input_hash=result.provenance.input_hash))
        return result

    @application.post("/v1/disease-intelligence/disease-specific", response_model=DiseaseSpecificResponse)

    def disease_specific_intelligence(request: Request, req: DiseaseSpecificRequest, authorization: str | None = Header(default=None)):  # noqa
        active = current_config()
        if active.environment != "development":
            raise HTTPException(status_code=503, detail="Disease-specific intelligence disabled pending security and safety approval")
        authorize(active, authorization, req.tenant_id, req.patient_id, "disease:assess")
        if not req.synthetic or not req.tenant_id.startswith("synthetic-") or not req.patient_id.startswith("synthetic-"):
            raise HTTPException(status_code=403, detail="Only synthetic disease-specific intelligence is allowed")
        result = evaluate_disease_specific(req)
        application.state.metrics.inc("disease_specific_assessments")
        application.state.audit_sink.append(new_event("disease.assessed", request.state.correlation_id, req.tenant_id, req.patient_id, "abstained" if result.status == "ABSTAINED" else "completed", policy_version=result.pack_version, input_hash=result.provenance_hash))
        return result

    @application.post("/v1/disease-intelligence/approved-rules/evaluate", response_model=ClinicalRuleResponse)

    def approved_clinical_rules(request: Request, req: DiseaseSpecificRequest, authorization: str | None = Header(default=None)):  # noqa
        active = current_config()
        if active.environment != "development":
            raise HTTPException(status_code=503, detail="Clinical rules disabled pending clinical governance approval")
        authorize(active, authorization, req.tenant_id, req.patient_id, "disease:rules")
        if not req.synthetic or not req.tenant_id.startswith("synthetic-") or not req.patient_id.startswith("synthetic-"):
            raise HTTPException(status_code=403, detail="Only synthetic clinical rules are allowed")
        result = evaluate_diabetes_hypoglycemia(req)
        application.state.metrics.inc("approved_rule_evaluations")
        application.state.audit_sink.append(new_event("disease.rules_evaluated", request.state.correlation_id, req.tenant_id, req.patient_id, "abstained" if result.abstained else "completed", policy_version=result.ruleset_version, input_hash=result.provenance_hash))
        return result

    @application.post("/v1/clinical-intelligence/synthetic-workflow", response_model=ClinicalWorkflowResponse)

    def synthetic_clinical_workflow(request: Request, req: ClinicalWorkflowRequest, authorization: str | None = Header(default=None)):  # noqa
        active = current_config()
        if active.environment != "development":
            raise HTTPException(status_code=503, detail="Clinical intelligence orchestration disabled pending security and safety approval")
        authorize(active, authorization, req.tenant_id, req.patient_id, "clinical-intelligence:execute")
        if not req.synthetic or not req.tenant_id.startswith("synthetic-") or not req.patient_id.startswith("synthetic-"):
            raise HTTPException(status_code=403, detail="Only synthetic clinical-intelligence workflows are allowed")
        application.state.audit_sink.append(new_event("clinical_workflow.requested", request.state.correlation_id, req.tenant_id, req.patient_id, "requested", policy_version="r7c-orchestration-v1"))
        application.state.metrics.inc("clinical_workflow_requests")
        result = execute_workflow(req, active, application.state.model_registry, gateway=ModelGateway(active, application.state.model_registry, application.state.metrics))
        event_status = "completed" if result.status == "COMPLETED_DRAFT" else "abstained"
        application.state.metrics.inc("clinical_workflow_completed" if result.status == "COMPLETED_DRAFT" else "clinical_workflow_abstentions")
        application.state.audit_sink.append(new_event("clinical_workflow.completed" if result.status == "COMPLETED_DRAFT" else "clinical_workflow.abstained", request.state.correlation_id, req.tenant_id, req.patient_id, event_status, model_id=(result.model_telemetry or {}).get("model"), policy_version="r7c-orchestration-v1", input_hash=result.provenance_hash))
        return result

    @application.post("/v1/clinical-workbench/synthetic", response_model=WorkbenchResponse)

    def synthetic_clinical_workbench(req: WorkbenchRequest, authorization: str | None = Header(default=None)):  # noqa
        active = current_config()
        authorize_workbench(active, authorization, req)
        return assemble_workbench(workbench_id=f"workbench-{uuid4()}", request=req)

    @application.post("/v1/reuse-accelerator/nocturne/diabetes-ingest", response_model=NocturneIngestResponse)

    def nocturne_diabetes_ingest(req: NocturneIngestRequest):  # noqa
        active = current_config()
        if active.environment != "development" or not req.synthetic or not req.tenant_id.startswith("synthetic-") or not req.patient_id.startswith("synthetic-"):
            raise HTTPException(status_code=403, detail="Only synthetic Nocturne-compatible ingestion is allowed")
        return ingest_nocturne(req)

    @application.post("/v1/reuse-accelerator/snomed-cds/evaluate", response_model=CdsPathwayResponse)

    def snomed_cds_contract(req: CdsPathwayRequest):  # noqa
        active = current_config()
        if active.environment != "development" or not req.synthetic or not req.tenant_id.startswith("synthetic-") or not req.patient_id.startswith("synthetic-"):
            raise HTTPException(status_code=403, detail="Only synthetic CDS contract evaluation is allowed")
        return evaluate_cds_pathway(req)

    @application.post("/v1/reuse-accelerator/ahrq-cql/execute", response_model=CqlExecutionResponse)

    def ahrq_cql_contract(req: CqlExecutionRequest):  # noqa
        active = current_config()
        if active.environment != "development" or not req.synthetic or not req.tenant_id.startswith("synthetic-") or not req.patient_id.startswith("synthetic-"):
            raise HTTPException(status_code=403, detail="Only synthetic CQL contract evaluation is allowed")
        return execute_cql_contract(req)

    @application.post("/v1/reuse-accelerator/fhir-cql/execute", response_model=StandardsCqlResponse)

    def fhir_cql_contract(req: StandardsCqlRequest):  # noqa
        active = current_config()
        if active.environment != "development" or not req.synthetic or not req.tenant_id.startswith("synthetic-") or not req.patient_id.startswith("synthetic-"):
            raise HTTPException(status_code=403, detail="Only synthetic FHIR/ELM execution is allowed")
        return execute_fhir_elm_subset(req)

    @application.post("/v1/reuse-accelerator/fhir-cql/upstream-runtime", response_model=UpstreamCqlRuntimeResponse)

    def upstream_fhir_cql_runtime(req: StandardsCqlRequest):  # noqa
        active = current_config()
        if active.environment != "development" or not req.synthetic or not req.tenant_id.startswith("synthetic-") or not req.patient_id.startswith("synthetic-"):
            raise HTTPException(status_code=403, detail="Only synthetic upstream CQL runtime execution is allowed")
        return execute_pinned_runtime(req)

    @application.post("/v1/reuse-accelerator/terminology/validate", response_model=TerminologyValidationResponse)

    def terminology_validate(req: TerminologyValidationRequest):  # noqa
        active = current_config()
        if active.environment != "development" or not req.synthetic or not req.tenant_id.startswith("synthetic-"):
            raise HTTPException(status_code=403, detail="Only synthetic terminology validation is allowed")
        return validate_code(req)

    @application.post("/v1/reuse-accelerator/unified-assess", response_model=UnifiedAssessmentResponse)

    def unified_disease_assessment(req: UnifiedAssessmentRequest):  # noqa
        active = current_config()
        if active.environment != "development" or not req.synthetic or not req.tenant_id.startswith("synthetic-") or not req.patient_id.startswith("synthetic-"):
            raise HTTPException(status_code=403, detail="Only synthetic unified assessment is allowed")
        return unified_assessment(req)

    @application.get("/v1/providers/{provider}/ready")

    def provider_ready(provider: str):  # noqa
        active = current_config()
        if provider == "medgemma":
            return {"provider": provider, "model": active.medgemma_model, "ready": MedGemmaProvider(active).ready()}
        if provider == "gemini":
            return {"provider": provider, "model": active.gemini_model, "ready": bool(active.gemini_api_key)}
        if provider in {"openai-compatible", "vllm", "llama.cpp"}:
            return {"provider": "openai-compatible", "model": active.openai_compatible_model, "ready": OpenAICompatibleProvider(active).ready()}
        raise HTTPException(status_code=404, detail="unknown provider")

    @application.post("/v1/snapshots", response_model=SnapshotResponse)

    def create_snapshot(request: Request, req: SnapshotRequest, authorization: str | None = Header(default=None)):  # noqa
        active = current_config()
        if active.environment != "development":
            raise HTTPException(status_code=503, detail="Clinical inference disabled pending security and safety approval")
        authorize(active, authorization, req.tenant_id, req.patient_id, "snapshot:write")
        if not req.synthetic or not req.patient_id.startswith("synthetic-") or not req.tenant_id.startswith("synthetic-"):
            raise HTTPException(status_code=403, detail="Only synthetic test records are allowed")
        result = SnapshotResponse(
            snapshot_id=str(uuid4()), patient_id=req.patient_id, tenant_id=req.tenant_id,
            facts=req.facts,
            summary="Synthetic evidence assembled for engineering validation only. No AI inference or clinical interpretation performed.",
            model_id="deterministic-dev-stub-v0",
        )
        application.state.audit_sink.append(new_event("snapshot.created", request.state.correlation_id, req.tenant_id, req.patient_id, "draft", model_id=result.model_id))
        return result

    @application.post("/v1/knowledge/ground", response_model=GroundingResponse)

    def ground_knowledge(request: Request, req: GroundingRequest, authorization: str | None = Header(default=None)):  # noqa
        active = current_config()
        if active.environment != "development":
            raise HTTPException(status_code=503, detail="Knowledge grounding disabled pending security and safety approval")
        authorize(active, authorization, req.tenant_id, req.patient_id, "knowledge:query")
        if not req.synthetic or not req.tenant_id.startswith("synthetic-") or not req.patient_id.startswith("synthetic-"):
            raise HTTPException(status_code=403, detail="Only synthetic knowledge grounding is allowed")
        result = ground(req)
        application.state.metrics.inc("knowledge_queries")
        application.state.metrics.inc("knowledge_abstentions" if result.abstained else "knowledge_grounded")
        application.state.audit_sink.append(new_event("knowledge.grounded" if not result.abstained else "knowledge.abstained", request.state.correlation_id, req.tenant_id, req.patient_id, "abstained" if result.abstained else "completed", input_hash=result.query_hash))
        return result

    @application.post("/v1/imaging/analyze", response_model=ImagingAnalysisResponse)

    def analyze_imaging(request: Request, req: ImagingAnalysisRequest, authorization: str | None = Header(default=None)):  # noqa
        active = current_config()
        if active.environment != "development":
            raise HTTPException(status_code=503, detail="Imaging analysis disabled pending security and safety approval")
        authorize(active, authorization, req.tenant_id, req.patient_id, "imaging:analyze")
        if not req.synthetic or not req.tenant_id.startswith("synthetic-") or not req.patient_id.startswith("synthetic-") or not req.study.synthetic:
            raise HTTPException(status_code=403, detail="Only synthetic imaging analysis is allowed")
        request_hash = imaging_input_hash(req)
        quality = assess_quality(req.study)
        workflow = plan_workflow(req)
        report = compose_report(req) if quality.passed else None
        segmentation = compose_segmentation_job(req) if quality.passed else None
        if not quality.passed:
            reason = "Image-quality gate failed: " + ", ".join(quality.reasons)
        elif req.task == "report_draft" and report is not None:
            reason = "Structured draft composed from supplied observations; clinician review is required."
        elif req.task == "quality_check":
            reason = "Metadata quality checks passed; no clinical interpretation performed."
        elif req.task == "segmentation_draft" and segmentation is not None and segmentation.status == "QUEUED":
            reason = "Segmentation job contract accepted; no mask generated until a validated adapter is configured."
        else:
            reason = "No imaging model is enabled; task abstained pending modality-specific validation and clinician review."
        status = "DRAFT" if quality.passed and (req.task == "quality_check" or report is not None or (segmentation is not None and segmentation.status == "QUEUED")) else "ABSTAINED"
        model_id = "deterministic-imaging-draft-v1" if status == "DRAFT" else "unconfigured-imaging-model"
        workflow = [step.model_copy(update={"status": "COMPLETED" if step.tool_id == "image-quality-gate" and quality.passed else ("ABSTAINED" if status == "ABSTAINED" else step.status)}) for step in workflow]
        result = ImagingAnalysisResponse(
            analysis_id=str(uuid4()), status=status, task=req.task, findings=report.findings if report else [], mask_references=[], reason=reason,
            quality=quality, workflow=workflow, report=report, segmentation=segmentation,
            provenance=ImagingProvenance(input_hash=request_hash, policy_version="r2-imaging-contract-v1", model_id=model_id, correlation_id=request.state.correlation_id),
        )
        application.state.metrics.inc("imaging_requests")
        application.state.metrics.inc("imaging_abstentions" if status == "ABSTAINED" else "imaging_drafts")
        application.state.audit_sink.append(new_event("imaging.abstained", request.state.correlation_id, req.tenant_id, req.patient_id, "abstained", model_id=result.provenance.model_id, policy_version=result.provenance.policy_version, input_hash=request_hash))
        return result

    @application.post("/v1/decisions", response_model=DecisionResponse)

    def create_decision(request: Request, req: DecisionRequest, authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):  # noqa
        active = current_config()
        if active.environment != "development":
            raise HTTPException(status_code=503, detail="Clinical inference disabled pending security and safety approval")
        authorize(active, authorization, req.tenant_id, req.patient_id, "decision:execute")
        try:
            policy_check(req)
        except ValueError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None

        output: DecisionModelOutput
        request_hash = input_hash(req)
        replay_key = idempotency_key or request_hash
        previous = application.state.decision_requests.get(replay_key)
        if previous is not None:
            previous_hash, previous_response = previous
            if previous_hash != request_hash:
                raise HTTPException(status_code=409, detail="decision request identity already used for different content")
            application.state.metrics.inc("decision_replays")
            return previous_response
        model_id = "deterministic-dev-stub-v0"
        decision_telemetry: DecisionTelemetry
        if not req.evidence:
            output = DecisionModelOutput(selected_option=None, rationale="Evidence grounding is required; workflow abstained.", abstained=True)
            decision_telemetry = DecisionTelemetry(request_id=f"policy-{uuid4()}", provider="policy", model=model_id, status="policy_abstained", latency_ms=0, schema_validated=False)
        elif not active.inference_enabled:
            output = DecisionModelOutput(selected_option=None, rationale="Inference is disabled; workflow abstained.", abstained=True)
            decision_telemetry = DecisionTelemetry(request_id=f"policy-{uuid4()}", provider="policy", model=model_id, status="policy_abstained", latency_ms=0, schema_validated=False)
        else:
            prompt = f"Question: {req.question}\nPermitted options: {req.permitted_options}\nSynthetic context: {req.context}\nReturn only the requested JSON object."
            try:
                output, telemetry = ModelGateway(active, application.state.model_registry, application.state.metrics).infer(req.provider, prompt, DecisionModelOutput, system_prompt="Make only non-diagnostic workflow decisions. Abstain when evidence is insufficient.")
                application.state.metrics.inc("inference_successes")
                if telemetry.schema_validated:
                    application.state.metrics.inc("inference_schema_validated")
                model_id = telemetry.model
                decision_telemetry = DecisionTelemetry(request_id=telemetry.request_id, provider=telemetry.provider, model=telemetry.model, status="inference_success", latency_ms=telemetry.latency_ms, schema_validated=telemetry.schema_validated, route_attempts=[DecisionRouteAttempt(**asdict(item)) for item in telemetry.route_attempts], retry_count=telemetry.retry_count)
            except ProviderError as exc:
                application.state.metrics.inc("provider_failures")
                application.state.audit_sink.append(
                    new_event(
                        "decision.provider_failed",
                        request.state.correlation_id,
                        req.tenant_id,
                        req.patient_id,
                        "failed",
                        model_id=active.model_routing_order[0] if active.model_routing_order else "unresolved",
                        policy_version="r1-nondiagnostic-v1",
                        input_hash=request_hash,
                    )
                )
                raise HTTPException(status_code=502, detail=f"{exc.provider}:{exc.classification}") from None
            output = validate_output(output, req)
        output = validate_output(output, req)
        decision_id = str(uuid4())
        correlation_id = request.state.correlation_id
        event_type = "decision.abstained" if output.abstained else "decision.completed"
        application.state.metrics.inc("decisions")
        if output.abstained:
            application.state.metrics.inc("decision_abstentions")
        application.state.audit_sink.append(new_event(event_type, correlation_id, req.tenant_id, req.patient_id, "abstained" if output.abstained else "completed", model_id=model_id, policy_version="r1-nondiagnostic-v1", input_hash=request_hash))
        response = DecisionResponse(
            decision_id=decision_id, selected_option=output.selected_option, rationale=output.rationale,
            abstained=output.abstained, confidence=output.confidence, model_id=model_id,
            policy_version="r1-nondiagnostic-v1", evidence_refs=req.evidence_refs or [item.source_id for item in req.evidence], evidence=req.evidence,
            provenance=DecisionProvenance(generated_at=generated_at(), input_hash=request_hash, model_id=model_id, policy_version="r1-nondiagnostic-v1", correlation_id=correlation_id, evidence_count=len(req.evidence)),
            telemetry=decision_telemetry,
        )
        application.state.decision_requests.put(replay_key, (request_hash, response))
        return response

    @application.post("/v1/trion/fhir-draft", response_model=TrionFhirDraftResponse)

    def create_trion_draft(request: Request, req: TrionFhirDraftRequest, authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):  # noqa
        active = current_config()
        if active.environment != "development":
            raise HTTPException(status_code=503, detail="TRION clinical draft boundary disabled pending security and safety approval")
        authorize_trion_boundary(active, authorization, req)
        if not req.synthetic or not req.tenant_id.startswith("synthetic-") or not req.patient_id.startswith("synthetic-"):
            raise HTTPException(status_code=403, detail="Only synthetic TRION requests are allowed")
        request_hash = sha256(json.dumps(req.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        replay_key = idempotency_key or request_hash
        previous = application.state.trion_requests.get(replay_key)
        if previous is not None:
            previous_hash, previous_response = previous
            if previous_hash != request_hash:
                raise HTTPException(status_code=409, detail="TRION request identity already used for different content")
            application.state.metrics.inc("trion_replays")
            return previous_response
        application.state.audit_sink.append(new_event("trion.requested", request.state.correlation_id, req.tenant_id, req.patient_id, "requested"))
        application.state.metrics.inc("trion_requests")
        payload = {"schemaVersion": 1, "documentId": req.document_id, "facts": [fact.model_dump(mode="json") for fact in req.facts], "generatedBy": "wysh.AI"}
        try:
            result = TrionClient(active).execute(payload, correlation_id=request.state.correlation_id, idempotency_key=idempotency_key)
            response = TrionFhirDraftResponse.model_validate(result.payload)
        except TrionError as exc:  # noqa
            application.state.metrics.inc("trion_failures")
            application.state.audit_sink.append(new_event("trion.failed", request.state.correlation_id, req.tenant_id, req.patient_id, "failed"))
            raise HTTPException(status_code=503, detail="TRION boundary unavailable") from None
        application.state.trion_requests.put(replay_key, (request_hash, response))
        application.state.metrics.inc("trion_successes")
        application.state.audit_sink.append(new_event("trion.completed", request.state.correlation_id, req.tenant_id, req.patient_id, "completed", model_id=response.model))
        return response

    return application


app = create_app()
