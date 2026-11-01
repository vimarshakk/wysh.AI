"""Synthetic-only shared engine for Phase-1 disease-pack assessments.

The engine reports data quality, temporal trends, and review gaps. It does not
diagnose, calculate clinical risk, recommend treatment, or commit actions.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .disease_intelligence import LongitudinalMeasurement, MonitoringRequest


class DiseasePack(BaseModel):
    disease_id: str
    pack_version: str
    supported_metrics: list[str]
    required_for_review: list[str]
    draft_actions: list[str]


class ClinicalAssessmentRequest(MonitoringRequest):
    as_of: str | None = None


class ClinicalFinding(BaseModel):
    code: str
    severity: Literal["INFO", "REVIEW", "ABSTAIN"]
    message: str
    evidence_refs: list[str]


class DraftCarePlan(BaseModel):
    draft_only: Literal[True] = True
    clinician_approval_required: Literal[True] = True
    proposed_actions: list[str]
    blocked_actions: list[str] = ["diagnose", "prescribe", "change treatment", "send referral", "write clinical record"]


class AssessmentProvenance(BaseModel):
    input_hash: str
    engine_version: str
    evidence_refs: list[str]
    synthetic_only: Literal[True] = True


class ClinicalAssessmentResponse(BaseModel):
    assessment_id: str
    disease_id: str
    pack_version: str
    findings: list[ClinicalFinding]
    missing_metrics: list[str]
    follow_up_status: Literal["REVIEW_REQUIRED", "NO_GAP_DETECTED", "ABSTAINED"]
    care_plan: DraftCarePlan | None
    abstained: bool
    rationale: str
    provenance: AssessmentProvenance
    clinical_use_authorized: Literal[False] = False
    human_review_required: Literal[True] = True


def _root() -> Path:
    return Path(__file__).parents[3]


def load_phase1_packs() -> dict[str, DiseasePack]:
    payload = json.loads((_root() / "disease-intelligence/packs/phase1-packs.json").read_text(encoding="utf-8"))
    return {item["disease_id"]: DiseasePack.model_validate(item) for item in payload["packs"]}


def _convert(metric: str, value: float, unit: str) -> tuple[float, str] | None:
    normalized = unit.strip().lower()
    if metric == "glucose" and normalized in {"mmol/l", "mmol\u00b7l-1"}:
        return round(value * 18.0182, 3), "mg/dL"
    if metric == "weight" and normalized in {"lb", "lbs", "pound", "pounds"}:
        return round(value * 0.45359237, 3), "kg"
    if metric == "creatinine" and normalized in {"umol/l", "µmol/l", "μmol/l"}:
        return round(value / 88.4, 4), "mg/dL"
    if metric == "uacr" and normalized in {"mg/mmol", "mg/mmol creatinine"}:
        return round(value * 8.84, 3), "mg/g"
    return value, unit


def normalize_measurements(measurements: list[LongitudinalMeasurement]) -> list[LongitudinalMeasurement]:
    result: list[LongitudinalMeasurement] = []
    for item in measurements:
        converted = _convert(item.metric, item.value, item.unit)
        if converted is None:
            continue
        value, unit = converted
        result.append(item.model_copy(update={"value": value, "unit": unit}))
    return result


def _hash(request: ClinicalAssessmentRequest, normalized: list[LongitudinalMeasurement]) -> str:
    payload = request.model_dump(mode="json")
    payload["measurements"] = [item.model_dump(mode="json") for item in normalized]
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def assess(request: ClinicalAssessmentRequest, now: datetime | None = None) -> ClinicalAssessmentResponse:
    packs = load_phase1_packs()
    pack = packs.get(request.disease_id)
    normalized = normalize_measurements(request.measurements)
    refs = [item.measurement_id for item in normalized]
    input_hash = _hash(request, normalized)
    if pack is None:
        return ClinicalAssessmentResponse(
            assessment_id=f"assessment-{request.disease_id}-{request.patient_id}", disease_id=request.disease_id, pack_version="none",
            findings=[ClinicalFinding(code="PACK_UNAVAILABLE", severity="ABSTAIN", message="No executable Phase-1 disease pack is configured.", evidence_refs=refs)],
            missing_metrics=[], follow_up_status="ABSTAINED", care_plan=None, abstained=True,
            rationale="The engine abstained because the requested disease pack is not enabled.",
            provenance=AssessmentProvenance(input_hash=input_hash, engine_version="phase1-engine-v1", evidence_refs=refs),
        )
    grouped: dict[str, list[LongitudinalMeasurement]] = defaultdict(list)
    for item in normalized:
        if item.metric in pack.supported_metrics:
            grouped[item.metric].append(item)
    missing = [metric for metric in pack.required_for_review if metric not in grouped]
    findings: list[ClinicalFinding] = []
    if missing:
        findings.append(ClinicalFinding(code="MISSING_REQUIRED_DATA", severity="REVIEW", message="Required measurements are missing; clinician review is needed.", evidence_refs=refs))
    if request.disease_id == "hypertension" and ("bp_systolic" in grouped) != ("bp_diastolic" in grouped):
        findings.append(ClinicalFinding(code="INCOMPLETE_BP_PAIR", severity="REVIEW", message="Systolic and diastolic values must be reviewed as a pair.", evidence_refs=[x.measurement_id for values in grouped.values() for x in values]))
    if request.disease_id == "diabetes" and "hba1c" in grouped and "glucose" in grouped:
        findings.append(ClinicalFinding(code="GLYCAEMIC_DATA_PRESENT", severity="INFO", message="HbA1c and glucose evidence are present for longitudinal review.", evidence_refs=[x.measurement_id for key in ("hba1c", "glucose") for x in grouped[key]]))
    if request.disease_id == "chronic-kidney-disease" and "egfr" in grouped and "urine_albumin" not in grouped:
        findings.append(ClinicalFinding(code="ALBUMINURIA_GAP", severity="REVIEW", message="Urine albumin evidence is missing for kidney-care review.", evidence_refs=[x.measurement_id for x in grouped["egfr"]]))
    current = now or datetime.now(timezone.utc)
    for metric, values in grouped.items():
        newest = max(values, key=lambda x: x.observed_at)
        observed = datetime.fromisoformat(newest.observed_at.replace("Z", "+00:00"))
        if (current - observed).days > 180:
            findings.append(ClinicalFinding(code="STALE_MEASUREMENT", severity="REVIEW", message=f"{metric} evidence is older than the six-month engineering follow-up window.", evidence_refs=[newest.measurement_id]))
    review = bool(findings)
    actions = pack.draft_actions if review else ["continue clinician-reviewed longitudinal monitoring"]
    return ClinicalAssessmentResponse(
        assessment_id=f"assessment-{request.disease_id}-{request.patient_id}", disease_id=request.disease_id, pack_version=pack.pack_version,
        findings=findings, missing_metrics=missing, follow_up_status="REVIEW_REQUIRED" if review else "NO_GAP_DETECTED",
        care_plan=DraftCarePlan(proposed_actions=actions), abstained=False,
        rationale="Synthetic, deterministic data-quality and follow-up assessment only; no diagnosis, risk score, treatment, prescription, referral, or record write was generated.",
        provenance=AssessmentProvenance(input_hash=input_hash, engine_version="phase1-engine-v1", evidence_refs=refs),
    )
