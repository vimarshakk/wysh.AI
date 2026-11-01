"""Synthetic-only longitudinal disease intelligence contracts and descriptive trends."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class DiseaseDefinition(BaseModel):
    id: str
    name: str
    priority: int = Field(ge=1, le=20)
    phase: Literal[1, 2, 3]
    population_scope: str
    tracking_domains: list[str] = Field(min_length=1)


class DiseaseCatalog(BaseModel):
    schema_version: str
    catalog_name: str
    clinical_use_authorized: bool
    prevalence_policy: str
    conditions: list[DiseaseDefinition]


class DiseaseWorkflow(BaseModel):
    disease_id: str
    workflow_version: str
    data_requirements: list[str]
    monitoring_plan: list[str]
    experiences: dict[str, list[str]]
    clinical_rules_status: str


class DiseaseWorkflowCatalog(BaseModel):
    schema_version: str
    clinical_use_authorized: bool
    workflows: list[DiseaseWorkflow]


class LongitudinalMeasurement(BaseModel):
    measurement_id: str = Field(min_length=1, max_length=200)
    metric: str = Field(min_length=1, max_length=100)
    value: float
    unit: str = Field(min_length=1, max_length=50)
    observed_at: str = Field(min_length=1, max_length=100)
    source_type: Literal["observation", "laboratory", "medication", "questionnaire", "encounter"]

    @field_validator("observed_at")
    @classmethod
    def valid_timestamp(cls, value: str) -> str:
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("observed_at must be an ISO-8601 timestamp") from None
        return value


class MonitoringRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=200)
    patient_id: str = Field(min_length=1, max_length=200)
    disease_id: str = Field(min_length=1, max_length=100)
    measurements: list[LongitudinalMeasurement] = Field(min_length=1, max_length=200)
    synthetic: bool = False
    application_profile: Literal["patient-companion", "clinician-copilot", "care-navigation", "operations", "research"] = "clinician-copilot"

    @field_validator("measurements")
    @classmethod
    def unique_measurements(cls, value: list[LongitudinalMeasurement]) -> list[LongitudinalMeasurement]:
        ids = [item.measurement_id for item in value]
        if len(set(ids)) != len(ids):
            raise ValueError("measurement_id values must be unique")
        return value


class TrendSummary(BaseModel):
    metric: str
    direction: Literal["UP", "DOWN", "STABLE", "INSUFFICIENT_DATA"]
    points: int
    first_value: float | None
    latest_value: float | None
    unit: str | None
    evidence_refs: list[str]


class MonitoringResponse(BaseModel):
    monitoring_id: str
    disease_id: str
    workflow_version: str
    trends: list[TrendSummary]
    missing_domains: list[str]
    interpretation_status: Literal["DESCRIPTIVE_ONLY"] = "DESCRIPTIVE_ONLY"
    rationale: str
    input_hash: str
    human_review_required: bool = True
    clinical_use_authorized: bool = False


def _root() -> Path:
    return Path(__file__).parents[3]


def load_disease_catalog() -> DiseaseCatalog:
    return DiseaseCatalog.model_validate_json((_root() / "disease-intelligence/registry/disease-catalog.json").read_text(encoding="utf-8"))


def load_phase1_workflows() -> DiseaseWorkflowCatalog:
    return DiseaseWorkflowCatalog.model_validate_json((_root() / "disease-intelligence/conditions/phase1-workflows.json").read_text(encoding="utf-8"))


def get_definition(disease_id: str) -> DiseaseDefinition:
    match = next((item for item in load_disease_catalog().conditions if item.id == disease_id), None)
    if match is None:
        raise ValueError("unknown disease pack")
    return match


def get_workflow(disease_id: str) -> DiseaseWorkflow:
    match = next((item for item in load_phase1_workflows().workflows if item.disease_id == disease_id), None)
    if match is None:
        raise ValueError("workflow is not specified for this phase")
    return match


def monitoring_input_hash(request: MonitoringRequest) -> str:
    return sha256(json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def describe_monitoring(request: MonitoringRequest, workflow: DiseaseWorkflow) -> MonitoringResponse:
    grouped: dict[str, list[LongitudinalMeasurement]] = defaultdict(list)
    for item in request.measurements:
        grouped[item.metric].append(item)
    trends: list[TrendSummary] = []
    for metric, values in sorted(grouped.items()):
        values.sort(key=lambda item: item.observed_at)
        first, latest = values[0], values[-1]
        if len(values) < 2:
            direction = "INSUFFICIENT_DATA"
        elif latest.value > first.value:
            direction = "UP"
        elif latest.value < first.value:
            direction = "DOWN"
        else:
            direction = "STABLE"
        trends.append(TrendSummary(metric=metric, direction=direction, points=len(values), first_value=first.value, latest_value=latest.value, unit=latest.unit, evidence_refs=[item.measurement_id for item in values]))
    observed = set(grouped)
    missing = [domain for domain in workflow.data_requirements if domain not in observed and domain != "diagnosis_context"]
    return MonitoringResponse(
        monitoring_id=f"monitor-{request.disease_id}-{request.patient_id}", disease_id=request.disease_id, workflow_version=workflow.workflow_version,
        trends=trends, missing_domains=missing, rationale="Descriptive trends only; no diagnosis, risk score, treatment, prescription, or escalation was generated.", input_hash=monitoring_input_hash(request),
    )
