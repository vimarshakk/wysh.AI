"""Original adapter contracts inspired by reviewed open-source patterns.

These adapters do not import source code, clinical content, model weights, or
undocumented endpoints from external projects.
"""

from __future__ import annotations

from collections import Counter  # noqa
from datetime import datetime  # noqa
from hashlib import sha256
import json
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator  # noqa

from .clinical_engine import ClinicalAssessmentResponse, ClinicalAssessmentRequest, assess
from .disease_intelligence import LongitudinalMeasurement


class NocturneGlucoseEntry(BaseModel):
    entry_id: str = Field(min_length=1, max_length=200)
    value: float
    unit: Literal["mg/dL", "mmol/L"]
    observed_at: str


class NocturneIngestRequest(BaseModel):
    tenant_id: str
    patient_id: str
    synthetic: bool = False
    entries: list[NocturneGlucoseEntry] = Field(min_length=1, max_length=1000)


class NocturneIngestResponse(BaseModel):
    adapter: Literal["nocturne-compatible"] = "nocturne-compatible"
    measurements: list[LongitudinalMeasurement]
    analytics: dict[str, Any]
    provenance_hash: str
    synthetic_only: Literal[True] = True
    clinical_use_authorized: Literal[False] = False


def ingest_nocturne(request: NocturneIngestRequest, lower_bound: float | None = None, upper_bound: float | None = None) -> NocturneIngestResponse:
    measurements = [LongitudinalMeasurement(measurement_id=item.entry_id, metric="glucose", value=item.value, unit=item.unit, observed_at=item.observed_at, source_type="observation") for item in request.entries]
    analytics: dict[str, Any] = {"points": len(measurements), "status": "DESCRIPTIVE_ONLY"}
    if lower_bound is None or upper_bound is None:
        analytics["range_status"] = "NOT_CONFIGURED"
    else:
        in_range = sum(lower_bound <= item.value <= upper_bound for item in measurements)
        analytics["range_status"] = "ENGINEERING_RANGE_ONLY"
        analytics["range_bounds"] = {"lower": lower_bound, "upper": upper_bound, "unit": measurements[0].unit}
        analytics["percent_in_configured_range"] = round((in_range / len(measurements)) * 100, 2)
    digest = sha256(json.dumps([item.model_dump(mode="json") for item in measurements], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return NocturneIngestResponse(measurements=measurements, analytics=analytics, provenance_hash=digest)


class CdsPathwayRequest(BaseModel):
    tenant_id: str
    patient_id: str
    pathway_id: str = Field(min_length=1, max_length=200)
    measurements: list[LongitudinalMeasurement] = Field(default_factory=list, max_length=200)
    synthetic: bool = False


class CdsPathwayResponse(BaseModel):
    adapter: Literal["snomed-fhir-cds-contract"] = "snomed-fhir-cds-contract"
    pathway_id: str
    status: Literal["CONTRACT_ONLY", "ABSTAINED"]
    notifications: list[dict[str, Any]]
    evidence_refs: list[str]
    reason: str
    clinical_use_authorized: Literal[False] = False


def evaluate_cds_pathway(request: CdsPathwayRequest) -> CdsPathwayResponse:
    return CdsPathwayResponse(pathway_id=request.pathway_id, status="CONTRACT_ONLY", notifications=[], evidence_refs=[item.measurement_id for item in request.measurements], reason="No external SNOMED pathway or clinical content is configured; the pathway was not executed. Configure and independently verify a licensed ruleset before enabling.")


class CqlExecutionRequest(BaseModel):
    tenant_id: str
    patient_id: str
    library_id: str = Field(min_length=1, max_length=200)
    expression_id: str = Field(min_length=1, max_length=200)
    facts: list[dict[str, Any]] = Field(default_factory=list, max_length=200)
    synthetic: bool = False


class CqlExecutionResponse(BaseModel):
    adapter: Literal["ahrq-cql-contract"] = "ahrq-cql-contract"
    status: Literal["EXECUTED_SYNTHETIC_SUBSET", "UNCONFIGURED", "ABSTAINED"] = "UNCONFIGURED"
    result: dict[str, Any] | None = None
    reason: str
    facts_hash: str
    clinical_use_authorized: Literal[False] = False


def execute_cql_contract(request: CqlExecutionRequest) -> CqlExecutionResponse:
    facts_hash = sha256(json.dumps(request.facts, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if request.library_id == "wysh.synthetic.rules.v1":
        numeric_values = [fact.get("value") for fact in request.facts if isinstance(fact.get("value"), (int, float)) and not isinstance(fact.get("value"), bool)]
        metric_facts = [fact for fact in request.facts if isinstance(fact.get("metric"), str)]
        if request.expression_id == "count-facts":
            return CqlExecutionResponse(status="EXECUTED_SYNTHETIC_SUBSET", result={"count": len(request.facts), "evidence_refs": [str(fact["id"]) for fact in request.facts if isinstance(fact.get("id"), str)]}, reason="Allowlisted synthetic CQL-subset expression executed by the pinned wysh.AI evaluator.", facts_hash=facts_hash)
        if request.expression_id == "mean-numeric":
            if not numeric_values:
                return CqlExecutionResponse(status="ABSTAINED", result=None, reason="The allowlisted mean expression abstained because no numeric facts were supplied.", facts_hash=facts_hash)
            return CqlExecutionResponse(status="EXECUTED_SYNTHETIC_SUBSET", result={"mean": round(sum(numeric_values) / len(numeric_values), 3), "count": len(numeric_values), "evidence_refs": [str(fact["id"]) for fact in request.facts if isinstance(fact.get("id"), str)]}, reason="Allowlisted synthetic CQL-subset expression executed by the pinned wysh.AI evaluator.", facts_hash=facts_hash)
        if request.expression_id == "has-glucose":
            refs = [str(fact["id"]) for fact in metric_facts if fact.get("metric") == "glucose" and isinstance(fact.get("id"), str)]
            return CqlExecutionResponse(status="EXECUTED_SYNTHETIC_SUBSET", result={"present": bool(refs), "evidence_refs": refs}, reason="Allowlisted synthetic CQL-subset expression executed by the pinned wysh.AI evaluator.", facts_hash=facts_hash)
    return CqlExecutionResponse(reason="CQL service adapter is intentionally unconfigured; no CQL library, executable content, or external endpoint was copied or invoked.", facts_hash=facts_hash)


class UnifiedAssessmentRequest(BaseModel):
    tenant_id: str
    patient_id: str
    disease_ids: list[str] = Field(min_length=1, max_length=3)
    measurements: list[LongitudinalMeasurement] = Field(min_length=1, max_length=300)
    synthetic: bool = False


class UnifiedAssessmentResponse(BaseModel):
    longitudinal_timeline: list[LongitudinalMeasurement]
    assessments: list[ClinicalAssessmentResponse]
    review_indicators: list[str]
    risk_indicators_status: Literal["NOT_CONFIGURED"] = "NOT_CONFIGURED"
    unified_input_hash: str
    synthetic_only: Literal[True] = True
    clinical_use_authorized: Literal[False] = False


def unified_assessment(request: UnifiedAssessmentRequest) -> UnifiedAssessmentResponse:
    assessments = [assess(ClinicalAssessmentRequest(tenant_id=request.tenant_id, patient_id=request.patient_id, disease_id=disease_id, measurements=request.measurements, synthetic=True)) for disease_id in request.disease_ids]
    timeline = sorted(request.measurements, key=lambda item: item.observed_at)
    indicators = sorted({finding.code for assessment in assessments for finding in assessment.findings})
    digest = sha256(json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return UnifiedAssessmentResponse(longitudinal_timeline=timeline, assessments=assessments, review_indicators=indicators, unified_input_hash=digest)
