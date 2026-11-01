"""Evidence-linked clinical rule vertical slice, held to synthetic engineering scope."""

from __future__ import annotations

from hashlib import sha256
import json
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from .clinical_engine import normalize_measurements
from .disease_intelligence import LongitudinalMeasurement
from .disease_specific_intelligence import DiseaseSpecificRequest


RULESET_VERSION = "r6a-diabetes-hypoglycemia-v1"
EVIDENCE_ID = "ada-soc-2026-hypoglycemia"


class ClinicalRuleFinding(BaseModel):
    rule_id: str
    severity: Literal["REVIEW", "ABSTAIN"]
    status: Literal["TRIGGERED", "NOT_TRIGGERED", "ABSTAINED"]
    message: str
    evidence_id: str
    evidence_refs: list[str]
    blocked_actions: list[str] = ["diagnose", "prescribe", "change treatment", "send referral", "emergency instruction"]


class ClinicalRuleResponse(BaseModel):
    assessment_id: str
    disease_id: str
    ruleset_version: str
    evidence_id: str
    approval_status: Literal["ENGINEERING_ONLY", "CLINICALLY_REVIEWED"]
    findings: list[ClinicalRuleFinding]
    abstained: bool
    rationale: str
    provenance_hash: str
    synthetic_only: Literal[True] = True
    clinical_use_authorized: Literal[False] = False
    clinician_review_required: Literal[True] = True
    interpretation_scope: Literal["OBSERVATION_CLASSIFICATION_ONLY"] = "OBSERVATION_CLASSIFICATION_ONLY"
    episode_diagnosis: Literal[False] = False


def _hash(request: DiseaseSpecificRequest, normalized: list[LongitudinalMeasurement]) -> str:
    payload = request.model_dump(mode="json")
    payload["measurements"] = [item.model_dump(mode="json") for item in normalized]
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def evaluate_diabetes_hypoglycemia(request: DiseaseSpecificRequest) -> ClinicalRuleResponse:
    normalized = normalize_measurements(request.measurements)
    provenance_hash = _hash(request, normalized)
    base = dict(assessment_id=f"rule-{request.disease_id}-{request.patient_id}", disease_id=request.disease_id, ruleset_version=RULESET_VERSION, evidence_id=EVIDENCE_ID, approval_status="ENGINEERING_ONLY", provenance_hash=provenance_hash)
    if request.disease_id != "diabetes":
        return ClinicalRuleResponse(**base, findings=[ClinicalRuleFinding(rule_id="diabetes.hypoglycemia-observation", severity="ABSTAIN", status="ABSTAINED", message="This rule vertical slice is limited to the diabetes workflow.", evidence_id=EVIDENCE_ID, evidence_refs=[])], abstained=True, rationale="Rule execution abstained because the disease scope is not applicable.")
    glucose = [item for item in normalized if item.metric == "glucose" and item.unit == "mg/dL"]
    if not glucose:
        return ClinicalRuleResponse(**{**base, "assessment_id": f"rule-diabetes-{request.patient_id}", "disease_id": "diabetes"}, findings=[ClinicalRuleFinding(rule_id="diabetes.hypoglycemia-observation", severity="ABSTAIN", status="ABSTAINED", message="The rule abstained because no supported glucose observation was supplied.", evidence_id=EVIDENCE_ID, evidence_refs=[])], abstained=True, rationale="Required glucose evidence is missing or uses an unsupported unit.")
    try:
        as_of = datetime.fromisoformat(request.as_of.replace("Z", "+00:00")) if request.as_of else None
    except ValueError:
        return ClinicalRuleResponse(**base, findings=[ClinicalRuleFinding(rule_id="diabetes.hypoglycemia-observation", severity="ABSTAIN", status="ABSTAINED", message="The rule abstained because the assessment time is invalid.", evidence_id=EVIDENCE_ID, evidence_refs=[])], abstained=True, rationale="A timezone-aware ISO-8601 assessment time is required.")
    if as_of is not None and as_of.tzinfo is None:
        return ClinicalRuleResponse(**base, findings=[ClinicalRuleFinding(rule_id="diabetes.hypoglycemia-observation", severity="ABSTAIN", status="ABSTAINED", message="The rule abstained because the assessment time has no timezone.", evidence_id=EVIDENCE_ID, evidence_refs=[])], abstained=True, rationale="A timezone-aware assessment time is required.")
    by_timestamp: dict[str, list[LongitudinalMeasurement]] = defaultdict(list)
    for item in glucose:
        by_timestamp[item.observed_at].append(item)
    duplicate_refs = [item.measurement_id for values in by_timestamp.values() if len(values) > 1 for item in values]
    conflicts = [values for values in by_timestamp.values() if len({round(item.value, 3) for item in values}) > 1]
    if conflicts:
        refs = [item.measurement_id for values in conflicts for item in values]
        return ClinicalRuleResponse(**base, findings=[ClinicalRuleFinding(rule_id="diabetes.hypoglycemia-observation", severity="ABSTAIN", status="ABSTAINED", message="Conflicting glucose observations share a timestamp; the rule abstained.", evidence_id=EVIDENCE_ID, evidence_refs=refs)], abstained=True, rationale="Conflicting observations must be reconciled before classification.")
    stale = [item for item in glucose if as_of is not None and (as_of.astimezone(timezone.utc) - datetime.fromisoformat(item.observed_at.replace("Z", "+00:00")).astimezone(timezone.utc)).total_seconds() > 180 * 86400]
    if stale:
        return ClinicalRuleResponse(**base, findings=[ClinicalRuleFinding(rule_id="diabetes.hypoglycemia-observation", severity="ABSTAIN", status="ABSTAINED", message="Required glucose evidence is stale for this assessment.", evidence_id=EVIDENCE_ID, evidence_refs=[item.measurement_id for item in stale])], abstained=True, rationale="The rule abstained because supported glucose evidence is older than the six-month engineering window.")
    findings: list[ClinicalRuleFinding] = []
    for item in sorted(glucose, key=lambda value: value.observed_at):
        if item.value < 54:
            findings.append(ClinicalRuleFinding(rule_id="diabetes.hypoglycemia-observation", severity="REVIEW", status="TRIGGERED", message="A glucose observation is below the evidence-registry level-2 boundary; clinician review is required. No treatment instruction is generated.", evidence_id=EVIDENCE_ID, evidence_refs=[item.measurement_id]))
        elif item.value < 70:
            findings.append(ClinicalRuleFinding(rule_id="diabetes.hypoglycemia-observation", severity="REVIEW", status="TRIGGERED", message="A glucose observation is below the evidence-registry level-1 boundary; clinician review is required. No treatment instruction is generated.", evidence_id=EVIDENCE_ID, evidence_refs=[item.measurement_id]))
    if not findings:
        findings.append(ClinicalRuleFinding(rule_id="diabetes.hypoglycemia-observation", severity="REVIEW", status="NOT_TRIGGERED", message="No supported glucose observation crossed the configured engineering review boundary.", evidence_id=EVIDENCE_ID, evidence_refs=[item.measurement_id for item in glucose]))
    if duplicate_refs:
        findings.insert(0, ClinicalRuleFinding(rule_id="diabetes.hypoglycemia-observation", severity="REVIEW", status="NOT_TRIGGERED", message="Duplicate same-value observations share a timestamp; one observation is used for classification and review is required.", evidence_id=EVIDENCE_ID, evidence_refs=duplicate_refs))
    return ClinicalRuleResponse(**{**base, "assessment_id": f"rule-diabetes-{request.patient_id}", "disease_id": "diabetes"}, findings=findings, abstained=False, rationale="Evidence-linked synthetic observation classification only; no episode diagnosis, risk prediction, treatment, prescription, referral, or emergency instruction was generated.")


def evidence_registry_path() -> Path:
    return Path(__file__).parents[3] / "disease-intelligence/evidence/clinical-evidence-registry-v1.json"
