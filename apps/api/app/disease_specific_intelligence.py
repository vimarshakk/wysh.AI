"""Disease-specific longitudinal data-quality intelligence for R5C.

The registry is an original, versioned contract. It intentionally stops at
observation quality, descriptive trends, and transparent derived values. No
thresholds, diagnosis, risk prediction, treatment, or autonomous escalation is
implemented here.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from hashlib import sha256
import json
from math import isfinite
from typing import Literal

from pydantic import BaseModel, Field

from .disease_intelligence import LongitudinalMeasurement, MonitoringRequest


DISEASE_SPEC_VERSION = "r5c-disease-specific-v1"


class DiseaseSpecificPack(BaseModel):
    disease_id: str
    schema_version: str = DISEASE_SPEC_VERSION
    observation_metrics: list[str]
    required_metrics: list[str]
    unit_allowlist: dict[str, list[str]]
    derived_metrics: list[str] = Field(default_factory=list)
    limitations: list[str]


class DiseaseSpecificFinding(BaseModel):
    code: str
    severity: Literal["INFO", "REVIEW", "ABSTAIN"]
    message: str
    evidence_refs: list[str]


class DiseaseSpecificTrend(BaseModel):
    metric: str
    points: int
    direction: Literal["UP", "DOWN", "STABLE", "INSUFFICIENT_DATA"]
    delta: float | None
    unit: str | None
    evidence_refs: list[str]


class DerivedMetric(BaseModel):
    code: str
    value: float | None
    unit: str | None
    formula: str
    evidence_refs: list[str]
    status: Literal["CALCULATED", "ABSTAINED"]
    limitation: str


class DiseaseSpecificRequest(MonitoringRequest):
    as_of: str | None = None


class DiseaseSpecificResponse(BaseModel):
    assessment_id: str
    disease_id: str
    pack_version: str
    status: Literal["DATA_QUALITY_ONLY", "ABSTAINED"]
    findings: list[DiseaseSpecificFinding]
    missing_metrics: list[str]
    trends: list[DiseaseSpecificTrend]
    derived_metrics: list[DerivedMetric]
    limitations: list[str]
    provenance_hash: str
    synthetic_only: Literal[True] = True
    clinical_use_authorized: Literal[False] = False
    human_review_required: Literal[True] = True


_COMMON = ["observation", "laboratory", "questionnaire", "encounter", "medication"]
_SPECS: dict[str, DiseaseSpecificPack] = {}


def _register(disease_id: str, observation_metrics: list[str], required_metrics: list[str], units: dict[str, list[str]], derived: list[str] = [], limitations: list[str] | None = None) -> None:
    _SPECS[disease_id] = DiseaseSpecificPack(
        disease_id=disease_id, observation_metrics=observation_metrics, required_metrics=required_metrics,
        unit_allowlist=units, derived_metrics=derived,
        limitations=limitations or ["Data-quality and descriptive monitoring only; clinical interpretation requires a clinician and validated disease-specific evidence."],
    )


_register("diabetes", ["glucose", "hba1c", "weight", "egfr", "retinal_screening", "foot_screening"], ["glucose", "hba1c"], {"glucose": ["mg/dL", "mmol/L"], "hba1c": ["%"], "weight": ["kg", "lb"], "egfr": ["mL/min/1.73m2", "mL/min/1.73 m²"]}, ["A1C_TO_EAG"])
_register("prediabetes", ["glucose", "hba1c", "weight", "waist", "activity"], ["glucose", "hba1c"], {"glucose": ["mg/dL", "mmol/L"], "hba1c": ["%"], "weight": ["kg", "lb"], "waist": ["cm"]}, ["A1C_TO_EAG"])
_register("hypertension", ["bp_systolic", "bp_diastolic", "egfr", "creatinine", "medication_adherence"], ["bp_systolic", "bp_diastolic"], {"bp_systolic": ["mmHg"], "bp_diastolic": ["mmHg"], "egfr": ["mL/min/1.73m2", "mL/min/1.73 m²"], "creatinine": ["mg/dL", "µmol/L", "umol/L"]})
_register("dyslipidemia", ["ldl", "hdl", "total_cholesterol", "triglycerides", "medication_adherence"], ["ldl", "total_cholesterol"], {"ldl": ["mg/dL", "mmol/L"], "hdl": ["mg/dL", "mmol/L"], "total_cholesterol": ["mg/dL", "mmol/L"], "triglycerides": ["mg/dL", "mmol/L"]}, ["NON_HDL"])
_register("obesity", ["weight", "height", "bmi", "waist", "activity", "metabolic_markers"], ["weight", "height"], {"weight": ["kg", "lb"], "height": ["m", "cm"], "bmi": ["kg/m2", "kg/m²"], "waist": ["cm"]}, ["BMI"])
_register("chronic-kidney-disease", ["egfr", "creatinine", "urine_albumin", "bp_systolic", "bp_diastolic"], ["egfr", "urine_albumin"], {"egfr": ["mL/min/1.73m2", "mL/min/1.73 m²"], "creatinine": ["mg/dL", "µmol/L", "umol/L"], "urine_albumin": ["mg/g", "mg/mmol"]})
_register("anemia", ["hemoglobin", "ferritin", "iron", "symptoms", "follow_up"], ["hemoglobin"], {"hemoglobin": ["g/dL", "g/L"], "ferritin": ["ng/mL", "µg/L"], "iron": ["µg/dL", "umol/L"]})
_register("fatty-liver-disease", ["alt", "ast", "liver_enzymes", "metabolic_markers", "imaging", "fibrosis_assessment"], ["alt", "ast"], {"alt": ["U/L"], "ast": ["U/L"]}, ["ALT_AST_RATIO"])
_register("copd", ["fev1", "spirometry", "symptoms", "exacerbations", "inhaler_adherence"], ["spirometry"], {"fev1": ["L"], "spirometry": ["score", "L"]})
_register("hypothyroidism", ["tsh", "free_t4", "symptoms", "medication_adherence"], ["tsh", "free_t4"], {"tsh": ["mIU/L"], "free_t4": ["ng/dL", "pmol/L"]})
_register("coronary-artery-disease", ["symptoms", "ldl", "lipids", "medications", "events"], ["symptoms", "lipids"], {"ldl": ["mg/dL", "mmol/L"], "lipids": ["score", "present"]})
_register("heart-failure", ["weight", "symptoms", "fluid_status", "medications"], ["weight", "symptoms"], {"weight": ["kg", "lb"], "fluid_status": ["score", "present"]})
_register("stroke", ["function", "rehabilitation", "medications", "events"], ["function"], {"function": ["score", "points"]})
_register("asthma", ["symptoms", "peak_flow", "inhalers", "exacerbations"], ["symptoms", "peak_flow"], {"peak_flow": ["L/min"]})
_register("depression", ["symptoms", "function", "treatment_response", "safety_check"], ["symptoms", "function"], {"symptoms": ["score", "points"], "function": ["score", "points"], "safety_check": ["score", "present"]})
_register("anxiety", ["symptoms", "function", "treatment_response", "safety_check"], ["symptoms", "function"], {"symptoms": ["score", "points"], "function": ["score", "points"], "safety_check": ["score", "present"]})
_register("osteoarthritis", ["pain", "mobility", "function", "activity"], ["pain", "function"], {"pain": ["score", "points"], "mobility": ["score", "points"], "function": ["score", "points"]})
_register("pcos", ["cycles", "metabolic_markers", "symptoms", "medications"], ["cycles", "symptoms"], {"cycles": ["days", "count"], "symptoms": ["score", "points"]})
_register("childhood-undernutrition", ["height", "weight", "growth_velocity", "nutrition"], ["height", "weight"], {"height": ["cm", "m"], "weight": ["kg", "lb"]}, ["GROWTH_VELOCITY"] , ["Age-specific growth standards, dates, sex, and clinician review are required; this pack does not classify growth or nutrition status."])
_register("tuberculosis", ["treatment_adherence", "symptoms", "laboratory_follow_up", "events"], ["treatment_adherence", "laboratory_follow_up"], {"treatment_adherence": ["percent", "%", "score"], "laboratory_follow_up": ["score", "present"]})


def load_disease_specific_packs() -> dict[str, DiseaseSpecificPack]:
    return dict(_SPECS)


def _hash(request: DiseaseSpecificRequest, measurements: list[LongitudinalMeasurement]) -> str:
    payload = request.model_dump(mode="json")
    payload["measurements"] = [item.model_dump(mode="json") for item in measurements]
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _trend(metric: str, values: list[LongitudinalMeasurement]) -> DiseaseSpecificTrend:
    ordered = sorted(values, key=lambda item: item.observed_at)
    if len(ordered) < 2:
        direction: Literal["INSUFFICIENT_DATA"] = "INSUFFICIENT_DATA"
        delta = None
    else:
        delta = round(ordered[-1].value - ordered[0].value, 3)
        direction = "UP" if delta > 0 else "DOWN" if delta < 0 else "STABLE"
    return DiseaseSpecificTrend(metric=metric, points=len(ordered), direction=direction, delta=delta, unit=ordered[-1].unit if ordered else None, evidence_refs=[item.measurement_id for item in ordered])


def _derived(pack: DiseaseSpecificPack, grouped: dict[str, list[LongitudinalMeasurement]]) -> list[DerivedMetric]:
    latest = lambda metric: max(grouped[metric], key=lambda item: item.observed_at) if metric in grouped else None
    results: list[DerivedMetric] = []
    if "A1C_TO_EAG" in pack.derived_metrics and (item := latest("hba1c")) is not None and item.unit == "%" and item.value > 0:
        results.append(DerivedMetric(code="A1C_TO_EAG", value=round(28.7 * item.value - 46.7, 3), unit="mg/dL", formula="28.7 × HbA1c_percent − 46.7", evidence_refs=[item.measurement_id], status="CALCULATED", limitation="Approximate descriptive conversion only; no treatment target or diagnosis."))
    if "BMI" in pack.derived_metrics:
        weight, height = latest("weight"), latest("height")
        if weight and height:
            kg = weight.value * 0.45359237 if weight.unit in {"lb", "lbs"} else weight.value
            meters = height.value / 100 if height.unit == "cm" else height.value
            if kg > 0 and meters > 0:
                results.append(DerivedMetric(code="BMI", value=round(kg / (meters * meters), 3), unit="kg/m²", formula="weight_kg ÷ height_m²", evidence_refs=[weight.measurement_id, height.measurement_id], status="CALCULATED", limitation="Descriptive anthropometric calculation only; no classification or treatment recommendation."))
    if "NON_HDL" in pack.derived_metrics:
        total, hdl = latest("total_cholesterol"), latest("hdl")
        if total and hdl and total.unit == hdl.unit:
            results.append(DerivedMetric(code="NON_HDL", value=round(total.value - hdl.value, 3), unit=total.unit, formula="total_cholesterol − HDL", evidence_refs=[total.measurement_id, hdl.measurement_id], status="CALCULATED", limitation="Descriptive lipid calculation only; no risk classification or treatment recommendation."))
    if "ALT_AST_RATIO" in pack.derived_metrics:
        alt, ast = latest("alt"), latest("ast")
        if alt and ast and ast.value > 0:
            results.append(DerivedMetric(code="ALT_AST_RATIO", value=round(alt.value / ast.value, 3), unit="ratio", formula="ALT ÷ AST", evidence_refs=[alt.measurement_id, ast.measurement_id], status="CALCULATED", limitation="Descriptive laboratory ratio only; no liver diagnosis or staging."))
    if "GROWTH_VELOCITY" in pack.derived_metrics:
        heights = sorted(grouped.get("height", []), key=lambda item: item.observed_at)
        if len(heights) >= 2:
            days = (datetime.fromisoformat(heights[-1].observed_at.replace("Z", "+00:00")) - datetime.fromisoformat(heights[0].observed_at.replace("Z", "+00:00"))).days
            results.append(DerivedMetric(code="GROWTH_VELOCITY", value=round((heights[-1].value - heights[0].value) / days * 365, 3) if days > 0 else None, unit=f"{heights[-1].unit}/year", formula="change in height ÷ elapsed days × 365", evidence_refs=[item.measurement_id for item in heights], status="CALCULATED" if days > 0 else "ABSTAINED", limitation="Age-specific standards and clinician interpretation are required; no growth classification is generated."))
    return results


def evaluate(request: DiseaseSpecificRequest) -> DiseaseSpecificResponse:
    pack = load_disease_specific_packs().get(request.disease_id)
    normalized = list(request.measurements)
    provenance_hash = _hash(request, normalized)
    if pack is None:
        return DiseaseSpecificResponse(assessment_id=f"disease-specific-{request.disease_id}-{request.patient_id}", disease_id=request.disease_id, pack_version="none", status="ABSTAINED", findings=[DiseaseSpecificFinding(code="PACK_UNAVAILABLE", severity="ABSTAIN", message="No disease-specific pack is configured.", evidence_refs=[item.measurement_id for item in normalized])], missing_metrics=[], trends=[], derived_metrics=[], limitations=["The engine abstained because the disease-specific contract is unavailable."], provenance_hash=provenance_hash)  # noqa
    grouped: dict[str, list[LongitudinalMeasurement]] = defaultdict(list)
    for item in normalized:
        if item.metric in pack.observation_metrics:
            grouped[item.metric].append(item)
    refs = [item.measurement_id for item in normalized]
    missing = [metric for metric in pack.required_metrics if metric not in grouped]
    findings: list[DiseaseSpecificFinding] = []
    if missing:
        findings.append(DiseaseSpecificFinding(code="MISSING_REQUIRED_OBSERVATION", severity="REVIEW", message="Required disease-specific observations are missing; review is required.", evidence_refs=refs))
    for metric, values in grouped.items():
        allowed = pack.unit_allowlist.get(metric)
        if allowed and any(item.unit not in allowed for item in values):
            findings.append(DiseaseSpecificFinding(code="UNIT_REVIEW_REQUIRED", severity="REVIEW", message=f"One or more {metric} observations use an unsupported unit for this pack.", evidence_refs=[item.measurement_id for item in values]))
        if any(not isfinite(item.value) for item in values):
            findings.append(DiseaseSpecificFinding(code="NON_FINITE_OBSERVATION", severity="ABSTAIN", message=f"The {metric} series contains a non-finite value and was not interpreted.", evidence_refs=[item.measurement_id for item in values]))
    if request.disease_id in {"hypertension"} and ("bp_systolic" in grouped) != ("bp_diastolic" in grouped):
        findings.append(DiseaseSpecificFinding(code="INCOMPLETE_PAIR", severity="REVIEW", message="Blood-pressure observations must be reviewed as a pair.", evidence_refs=refs))
    trends = [_trend(metric, values) for metric, values in sorted(grouped.items())]
    derived = _derived(pack, grouped)
    status: Literal["DATA_QUALITY_ONLY", "ABSTAINED"] = "ABSTAINED" if any(item.severity == "ABSTAIN" for item in findings) else "DATA_QUALITY_ONLY"
    return DiseaseSpecificResponse(assessment_id=f"disease-specific-{request.disease_id}-{request.patient_id}", disease_id=request.disease_id, pack_version=pack.schema_version, status=status, findings=findings, missing_metrics=missing, trends=trends, derived_metrics=derived, limitations=pack.limitations, provenance_hash=provenance_hash)
