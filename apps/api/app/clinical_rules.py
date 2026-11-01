"""Original, deterministic rule interface for disease packs.

This intentionally implements completeness rules only. CQL/FHIR engines can be
connected behind this interface later; no copied CQL or clinical thresholds are
embedded here.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .disease_intelligence import MonitoringRequest


class ClinicalRule(BaseModel):
    id: str
    disease_id: str
    type: Literal["required_measurement", "required_measurement_group"]
    metric: str | None = None
    metrics: list[str] = Field(default_factory=list)
    label: str
    severity: Literal["INFO", "REVIEW"]


class ClinicalRuleSet(BaseModel):
    schema_version: str
    clinical_use_authorized: bool
    rules: list[ClinicalRule]


class RuleFinding(BaseModel):
    rule_id: str
    label: str
    severity: str
    status: Literal["SATISFIED", "MISSING_DATA"]
    missing_metrics: list[str]
    evidence_refs: list[str]


class RuleEvaluationResponse(BaseModel):
    evaluation_id: str
    disease_id: str
    ruleset_version: str
    findings: list[RuleFinding]
    review_required: bool
    interpretation_status: Literal["DETERMINISTIC_COMPLETENESS_ONLY"] = "DETERMINISTIC_COMPLETENESS_ONLY"
    rationale: str
    input_hash: str
    clinical_use_authorized: bool = False


def load_rules() -> ClinicalRuleSet:
    path = Path(__file__).parents[3] / "disease-intelligence/shared/clinical-rules-v1.json"
    return ClinicalRuleSet.model_validate_json(path.read_text(encoding="utf-8"))


def evaluate_rules(request: MonitoringRequest) -> RuleEvaluationResponse:
    ruleset = load_rules()
    rules = [rule for rule in ruleset.rules if rule.disease_id == request.disease_id]
    observed: dict[str, list[str]] = {}
    for measurement in request.measurements:
        observed.setdefault(measurement.metric, []).append(measurement.measurement_id)
    findings: list[RuleFinding] = []
    for rule in rules:
        required = [rule.metric] if rule.type == "required_measurement" and rule.metric else list(rule.metrics)
        missing = [metric for metric in required if metric not in observed]
        refs = [ref for metric in required if metric in observed for ref in observed[metric]]
        findings.append(RuleFinding(rule_id=rule.id, label=rule.label, severity=rule.severity, status="MISSING_DATA" if missing else "SATISFIED", missing_metrics=missing, evidence_refs=refs))
    canonical = request.model_dump(mode="json")
    request_hash = sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return RuleEvaluationResponse(
        evaluation_id=f"rules-{request.disease_id}-{request.patient_id}", disease_id=request.disease_id, ruleset_version=ruleset.schema_version,
        findings=findings, review_required=any(item.status == "MISSING_DATA" for item in findings),
        rationale="Deterministic measurement-completeness findings only; no diagnosis, risk score, treatment, or escalation was generated.", input_hash=request_hash,
    )
