"""Traceable synthetic clinical-intelligence orchestration.

This module composes existing wysh.AI contracts. It does not make a diagnosis,
recommend treatment, or turn a model response into an authorized decision.
Every stage is represented explicitly and any missing or unsafe stage causes a
fail-closed draft/abstention result.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
import time
from dataclasses import asdict
from typing import Any, Literal
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

from .fhir_adapter import FHIRMonitoringRequest, bundle_to_monitoring
from .gateway import ModelGateway
from .metrics import Metrics
from .providers import InferenceTelemetry, ProviderError
from .standards_cql import StandardsCqlRequest, StandardsCqlResponse, execute_fhir_elm_subset
from .terminology import TerminologyValidationRequest, TerminologyValidationResponse, validate_code, TERMINOLOGY_VERSION
from .upstream_cql_runtime import UpstreamCqlRuntimeResponse, execute_pinned_runtime
from .verified_calculations import CalculationRequest, VerifiedCalculationResponse, calculate


CLINICAL_ORCHESTRATION_VERSION = "r7d-orchestration-v1"
_ROOT = Path(__file__).parents[3]
_ELM_PATH = _ROOT / "disease-intelligence/cql/wysh-diabetes-glucose-observation-elm.json"
_UNSAFE_MODEL_LANGUAGE = re.compile(r"\b(diagnos(?:e|is|ed|ing)|prescrib|start medication|stop medication|change (?:the )?dose|emergency|treatment plan)\b", re.I)
_MODEL_INJECTION_LANGUAGE = re.compile(r"\b(ignore (?:all|any|the) previous instructions?|system prompt|developer message|reveal hidden|override safety)\b", re.I)
_MODEL_ACTION_LANGUAGE = re.compile(r"\b(take|use|start|stop|increase|decrease|change)\s+(?:insulin|metformin|medication|medicine|drug|dose|\d+\s*(?:mg|units?))\b", re.I)


class ClinicalWorkflowRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=200)
    patient_id: str = Field(min_length=1, max_length=200)
    disease_id: Literal["diabetes"] = "diabetes"
    bundle: dict[str, Any]
    age_years: int | None = Field(default=None, ge=18, le=120)
    sex: Literal["female", "male"] | None = None
    provider: str = Field(default="medgemma", min_length=1, max_length=40)
    synthetic: bool = False

    @field_validator("bundle")
    @classmethod
    def bundle_is_synthetic(cls, value: dict[str, Any]) -> dict[str, Any]:
        if value.get("resourceType") != "Bundle" or value.get("meta", {}).get("tag", [{}])[0].get("code") != "synthetic":
            raise ValueError("only explicitly synthetic FHIR Bundles are accepted")
        return value


StageStatus = Literal["COMPLETED", "ABSTAINED", "UNAVAILABLE", "NOT_CONFIGURED"]


class WorkflowStage(BaseModel):
    name: str
    status: StageStatus
    reason: str
    latency_ms: int = Field(ge=0)
    provenance_refs: list[str] = Field(default_factory=list)


class ClinicalExplanation(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=50, validation_alias=AliasChoices("evidence_refs", "references"))
    limitations: list[str] = Field(default_factory=list, max_length=20)
    abstained: bool = False
    unsupported_claims_blocked: Literal[True] = True
    draft_only: Literal[True] = True

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: Any) -> Any:
        return [value] if isinstance(value, str) else value

    @model_validator(mode="before")
    @classmethod
    def normalize_provider_status(cls, value: Any) -> Any:
        if isinstance(value, dict) and "abstained" not in value and isinstance(value.get("status"), str):
            value = dict(value)
            value["abstained"] = value["status"].lower() in {"abstained", "abstain", "blocked"}
        return value


class SafetyEvaluation(BaseModel):
    status: Literal["PASS", "ABSTAINED"]
    findings: list[str]
    checked_evidence_refs: list[str]
    policy_version: str = "r7c-model-safety-v1"


class ClinicalWorkflowResponse(BaseModel):
    workflow_id: str
    disease_id: str
    status: Literal["COMPLETED_DRAFT", "ABSTAINED", "MODEL_UNAVAILABLE"]
    stages: list[WorkflowStage]
    terminology: list[TerminologyValidationResponse]
    calculations: VerifiedCalculationResponse | None
    cql_native: StandardsCqlResponse | None
    cql_upstream: UpstreamCqlRuntimeResponse | None
    explanation: ClinicalExplanation | None
    safety: SafetyEvaluation
    provenance_hash: str
    review_required: Literal[True] = True
    review_state: Literal["DRAFT_ONLY"] = "DRAFT_ONLY"
    synthetic_only: Literal[True] = True
    clinical_use_authorized: Literal[False] = False
    model_telemetry: dict[str, Any] | None = None


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _stage(name: str, started: float, status: StageStatus, reason: str, refs: list[str] | None = None) -> WorkflowStage:
    return WorkflowStage(name=name, status=status, reason=reason, latency_ms=max(0, int((time.perf_counter() - started) * 1000)), provenance_refs=refs or [])


def _load_elm() -> dict[str, Any] | None:
    try:
        return json.loads(_ELM_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _has_actionable_match(pattern: re.Pattern[str], text: str) -> bool:
    """Reject actionable model language while allowing safety disclaimers."""
    for match in pattern.finditer(text):
        prefix = text[max(0, match.start() - 32):match.start()]
        if re.search(r"\b(?:no|not|never|without|don't|do not|does not|cannot|can't)\s*$", prefix, re.I):
            continue
        return True
    return False


def _model_safety(explanation: ClinicalExplanation, evidence_refs: set[str]) -> SafetyEvaluation:
    findings: list[str] = []
    unknown_refs = sorted(set(explanation.evidence_refs) - evidence_refs)
    if unknown_refs:
        findings.append("model cited evidence identifiers not present in the workflow")
    if _has_actionable_match(_UNSAFE_MODEL_LANGUAGE, explanation.summary):
        findings.append("model output contained diagnostic, treatment, or emergency language")
    if _MODEL_INJECTION_LANGUAGE.search(explanation.summary):
        findings.append("model output contained prompt-injection or instruction-override language")
    if _has_actionable_match(_MODEL_ACTION_LANGUAGE, explanation.summary):
        findings.append("model output contained medication or dose instructions")
    if not explanation.limitations:
        findings.append("model output omitted explicit limitations")
    if explanation.abstained and explanation.evidence_refs:
        findings.append("abstaining model output must not cite positive evidence as a conclusion")
    if findings:
        return SafetyEvaluation(status="ABSTAINED", findings=findings, checked_evidence_refs=sorted(evidence_refs))
    return SafetyEvaluation(status="PASS", findings=["typed output, evidence references, limitations, and non-diagnostic language passed deterministic safety checks"], checked_evidence_refs=sorted(evidence_refs))


def _model_prompt(calculations: VerifiedCalculationResponse, cql: StandardsCqlResponse, evidence_refs: list[str]) -> str:
    """Construct a compact structured prompt; raw FHIR and free text never enter the model."""
    payload = {
        "task": "summarize synthetic engineering evidence for clinician review",
        "disease": calculations.disease_id,
        "calculation_status": "ABSTAINED" if calculations.abstained else "COMPLETED",
        "calculations": [item.model_dump(mode="json") for item in calculations.calculations],
        "cql_status": cql.status,
        "cql_result": cql.result,
        "evidence_refs": evidence_refs,
        "required_output": "Return exactly the canonical keys summary (string), evidence_refs (array of supplied IDs), limitations (array of strings), abstained (boolean), unsupported_claims_blocked (true), and draft_only (true). Do not use alternate keys such as references or status. Use only supplied evidence refs. State limitations. Do not diagnose, prescribe, recommend treatment, or advise emergency action. Abstain if evidence is insufficient.",
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def execute_workflow(request: ClinicalWorkflowRequest, settings: Any, registry: Any, *, gateway: ModelGateway | None = None, metrics: Metrics | None = None) -> ClinicalWorkflowResponse:
    workflow_id = f"clinical-workflow-{uuid4()}"
    stages: list[WorkflowStage] = []
    terminology: list[TerminologyValidationResponse] = []
    calculations: VerifiedCalculationResponse | None = None
    cql_native: StandardsCqlResponse | None = None
    cql_upstream: UpstreamCqlRuntimeResponse | None = None
    explanation: ClinicalExplanation | None = None
    telemetry: InferenceTelemetry | None = None

    started = time.perf_counter()
    try:
        monitoring = bundle_to_monitoring(FHIRMonitoringRequest(tenant_id=request.tenant_id, patient_id=request.patient_id, disease_id=request.disease_id, bundle=request.bundle, synthetic=True))
    except (ValueError, TypeError, KeyError):
        stages.append(_stage("fhir_validation", started, "ABSTAINED", "Synthetic FHIR Bundle did not contain a supported typed observation."))
        safety = SafetyEvaluation(status="ABSTAINED", findings=["workflow stopped before interpretation because FHIR validation failed"], checked_evidence_refs=[])
        return ClinicalWorkflowResponse(workflow_id=workflow_id, disease_id=request.disease_id, status="ABSTAINED", stages=stages, terminology=[], calculations=None, cql_native=None, cql_upstream=None, explanation=None, safety=safety, provenance_hash=_digest({"workflow_id": workflow_id, "bundle": request.bundle}))
    observation_refs = [item.measurement_id for item in monitoring.measurements]
    stages.append(_stage("fhir_validation", started, "COMPLETED", "Synthetic FHIR R4 Bundle mapped to typed observations; raw Bundle is not retained in the response.", observation_refs))

    consistency_started = time.perf_counter()
    observed_values: dict[tuple[str, str], float] = {}
    conflicting_refs: list[str] = []
    for item in monitoring.measurements:
        key = (item.metric, item.observed_at)
        previous = observed_values.get(key)
        if previous is not None and previous != item.value:
            conflicting_refs.append(item.measurement_id)
        observed_values[key] = item.value
    data_consistent = not conflicting_refs
    stages.append(_stage("data_consistency", consistency_started, "COMPLETED" if data_consistent else "ABSTAINED", "No conflicting values share the same metric and timestamp." if data_consistent else "Conflicting values share the same metric and timestamp; interpretation abstained.", conflicting_refs or observation_refs))

    started = time.perf_counter()
    seen_codes: set[tuple[str, str]] = set()
    for entry in request.bundle.get("entry", []):
        resource = entry.get("resource", {}) if isinstance(entry, dict) else {}
        if resource.get("resourceType") != "Observation":
            continue
        for coding in resource.get("code", {}).get("coding", []):
            if not isinstance(coding, dict) or not coding.get("system") or not coding.get("code"):
                continue
            key = (str(coding["system"]), str(coding["code"]))
            if key in seen_codes:
                continue
            seen_codes.add(key)
            terminology.append(validate_code(TerminologyValidationRequest(tenant_id=request.tenant_id, system=key[0], code=key[1], display=coding.get("display"), value_set_url="https://wysh.ai/fhir/ValueSet/synthetic-diabetes-observations", synthetic=True)))
    required_codes = {item.code for item in terminology if item.system == "http://loinc.org" and item.code in {"2339-0", "4548-4"}}
    terminology_ok = bool(terminology) and "2339-0" in required_codes and required_codes.issubset({"2339-0", "4548-4"}) and all(item.status == "VALID" for item in terminology)
    terminology_refs = [f"terminology:{item.system}|{item.code}" for item in terminology]
    stages.append(_stage("terminology_validation", started, "COMPLETED" if terminology_ok else "ABSTAINED", TERMINOLOGY_VERSION if terminology_ok else "One or more required observation codes failed the synthetic terminology contract.", terminology_refs))

    started = time.perf_counter()
    calculations = calculate(CalculationRequest(tenant_id=request.tenant_id, patient_id=request.patient_id, disease_id=request.disease_id, measurements=monitoring.measurements, age_years=request.age_years, sex=request.sex, synthetic=True))
    stages.append(_stage("deterministic_calculations", started, "COMPLETED" if not calculations.abstained else "ABSTAINED", calculations.rationale, [ref for item in calculations.calculations for ref in item.evidence_refs]))

    elm = _load_elm()
    started = time.perf_counter()
    if elm is None:
        cql_native = None
        stages.append(_stage("cql_native", started, "UNAVAILABLE", "Pinned JSON ELM artifact is unavailable."))
    else:
        cql_request = StandardsCqlRequest(tenant_id=request.tenant_id, patient_id=request.patient_id, library_id="wysh.diabetes.rules", expression_id="HasGlucoseObservation", elm=elm, bundle=request.bundle, synthetic=True)
        cql_native = execute_fhir_elm_subset(cql_request)
        stages.append(_stage("cql_native", started, "COMPLETED" if cql_native.status.startswith("EXECUTED") else "ABSTAINED", cql_native.reason, cql_native.evidence_refs))

    started = time.perf_counter()
    if elm is None:
        cql_upstream = None
        stages.append(_stage("cql_upstream", started, "UNAVAILABLE", "Pinned JSON ELM artifact is unavailable."))
    else:
        cql_upstream = execute_pinned_runtime(StandardsCqlRequest(tenant_id=request.tenant_id, patient_id=request.patient_id, library_id="wysh.diabetes.rules", expression_id="HasGlucoseObservation", elm=elm, bundle=request.bundle, synthetic=True))
        stages.append(_stage("cql_upstream", started, "COMPLETED" if cql_upstream.status == "EXECUTED_UPSTREAM_RUNTIME" else cql_upstream.status.replace("EXECUTED", "COMPLETED"), cql_upstream.reason, cql_native.evidence_refs if cql_native else []))

    evidence_refs = sorted(set(observation_refs + [ref for item in calculations.calculations for ref in item.evidence_refs] + (cql_native.evidence_refs if cql_native else [])))
    model_cql = cql_native or StandardsCqlResponse(library_id="wysh.diabetes.rules", expression_id="HasGlucoseObservation", result=None, evidence_refs=[], elm_hash="unavailable", status="UNCONFIGURED", reason="No native CQL result was available.")
    started = time.perf_counter()
    if not settings.inference_enabled:
        stages.append(_stage("medgemma_explanation", started, "UNAVAILABLE", "Model inference is disabled by local configuration; no fallback was applied."))
        safety = SafetyEvaluation(status="ABSTAINED", findings=["model inference disabled; no explanation or approval was produced"], checked_evidence_refs=evidence_refs)
        return ClinicalWorkflowResponse(workflow_id=workflow_id, disease_id=request.disease_id, status="MODEL_UNAVAILABLE", stages=stages, terminology=terminology, calculations=calculations, cql_native=cql_native, cql_upstream=cql_upstream, explanation=None, safety=safety, provenance_hash=_digest({"workflow_id": workflow_id, "input": request.model_dump(mode="json"), "evidence_refs": evidence_refs}), model_telemetry=None)
    gateway = gateway or ModelGateway(settings, registry, metrics)
    try:
        explanation, telemetry = gateway.infer(request.provider, _model_prompt(calculations, model_cql, evidence_refs), ClinicalExplanation, system_prompt="You are a bounded clinical evidence summarizer. Return JSON only. Never diagnose, prescribe, recommend treatment, or invent evidence. Always state limitations and keep the output draft-only.")
        stages.append(_stage("medgemma_explanation", started, "COMPLETED", "Typed model output received; it remains a draft and is not clinical advice.", explanation.evidence_refs))
    except ProviderError as exc:
        stages.append(_stage("medgemma_explanation", started, "UNAVAILABLE", f"{exc.provider}:{exc.classification}"))
        safety = SafetyEvaluation(status="ABSTAINED", findings=["model stage unavailable; no explanation or approval was produced"], checked_evidence_refs=evidence_refs)
        return ClinicalWorkflowResponse(workflow_id=workflow_id, disease_id=request.disease_id, status="MODEL_UNAVAILABLE", stages=stages, terminology=terminology, calculations=calculations, cql_native=cql_native, cql_upstream=cql_upstream, explanation=None, safety=safety, provenance_hash=_digest({"workflow_id": workflow_id, "input": request.model_dump(mode="json"), "evidence_refs": evidence_refs}), model_telemetry=None)

    safety = _model_safety(explanation, set(evidence_refs))
    stages.append(_stage("safety_evaluation", started, "COMPLETED" if safety.status == "PASS" else "ABSTAINED", "; ".join(safety.findings), safety.checked_evidence_refs))
    overall = "COMPLETED_DRAFT" if safety.status == "PASS" and data_consistent and terminology_ok and calculations is not None and not calculations.abstained and cql_native is not None and cql_native.status.startswith("EXECUTED") else "ABSTAINED"
    if overall == "ABSTAINED":
        explanation = explanation.model_copy(update={"abstained": True, "evidence_refs": []})
    model_telemetry = ({**asdict(telemetry), "configured_model_version": getattr(settings, "medgemma_model_version", None)} if telemetry else None)
    provenance_hash = _digest({"workflow_id": workflow_id, "input": request.model_dump(mode="json"), "stage_provenance": [item.model_dump(mode="json") for item in stages], "terminology": [item.model_dump(mode="json") for item in terminology], "evidence_refs": evidence_refs, "model": model_telemetry})
    return ClinicalWorkflowResponse(workflow_id=workflow_id, disease_id=request.disease_id, status=overall, stages=stages, terminology=terminology, calculations=calculations, cql_native=cql_native, cql_upstream=cql_upstream, explanation=explanation, safety=safety, provenance_hash=provenance_hash, model_telemetry=model_telemetry)
