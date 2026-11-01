"""Versioned, reference-backed synthetic calculation contracts.

These calculations are intentionally separate from disease interpretation. They
return transparent values, formulas, inputs, and provenance; they do not label
patients, recommend care, or authorize clinical use.
"""

from __future__ import annotations

from hashlib import sha256
import json
from math import isfinite, pow
from typing import Literal

from pydantic import BaseModel, Field

from .clinical_engine import normalize_measurements
from .disease_intelligence import LongitudinalMeasurement, MonitoringRequest


CALCULATION_VERSION = "r4b-calculations-v1"
ADA_EAG_REFERENCE = "https://professional.diabetes.org/es/node/171"
NIDDK_EGFR_REFERENCE = "https://www.niddk.nih.gov/research-funding/research-programs/kidney-clinical-research-epidemiology/laboratory/glomerular-filtration-rate-equations/adults"


class CalculationRequest(MonitoringRequest):
    age_years: int | None = Field(default=None, ge=18, le=120)
    sex: Literal["female", "male"] | None = None


class CalculationResult(BaseModel):
    code: str
    status: Literal["CALCULATED", "ABSTAINED"]
    value: float | None
    unit: str | None
    formula: str
    reference_id: str
    evidence_refs: list[str]
    limitation: str


class CalculationProvenance(BaseModel):
    input_hash: str
    calculation_version: str = CALCULATION_VERSION
    synthetic_only: Literal[True] = True


class VerifiedCalculationResponse(BaseModel):
    calculation_id: str
    disease_id: str
    calculations: list[CalculationResult]
    abstained: bool
    rationale: str
    provenance: CalculationProvenance
    clinical_use_authorized: Literal[False] = False
    human_review_required: Literal[True] = True


def _input_hash(request: CalculationRequest, normalized: list[LongitudinalMeasurement]) -> str:
    payload = request.model_dump(mode="json")
    payload["measurements"] = [item.model_dump(mode="json") for item in normalized]
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _latest(measurements: list[LongitudinalMeasurement], metric: str) -> LongitudinalMeasurement | None:
    values = [item for item in measurements if item.metric == metric]
    return max(values, key=lambda item: item.observed_at) if values else None


def _result(code: str, value: float | None, unit: str | None, formula: str, reference_id: str, evidence_refs: list[str], limitation: str, status: Literal["CALCULATED", "ABSTAINED"] = "CALCULATED") -> CalculationResult:
    return CalculationResult(code=code, status=status, value=None if value is None else round(value, 3), unit=unit, formula=formula, reference_id=reference_id, evidence_refs=evidence_refs, limitation=limitation)


def _diabetes(measurements: list[LongitudinalMeasurement]) -> list[CalculationResult]:
    results: list[CalculationResult] = []
    glucose = [item for item in measurements if item.metric == "glucose" and item.unit.lower() == "mg/dl"]
    if glucose:
        results.append(_result("MEAN_GLUCOSE", sum(item.value for item in glucose) / len(glucose), "mg/dL", "mean(glucose_mg_dL)", "wysh.synthetic.mean-v1", [item.measurement_id for item in glucose], "Descriptive aggregation only; not a treatment target."))
    hba1c = _latest(measurements, "hba1c")
    if hba1c and hba1c.unit.strip() in {"%", "percent"}:
        results.append(_result("A1C_TO_EAG", 28.7 * hba1c.value - 46.7, "mg/dL", "eAG_mg_dL = 28.7 × HbA1c_percent − 46.7", ADA_EAG_REFERENCE, [hba1c.measurement_id], "Estimated average glucose is an approximation and requires clinician interpretation."))
    return results


def _hypertension(measurements: list[LongitudinalMeasurement]) -> list[CalculationResult]:
    results: list[CalculationResult] = []
    systolic = [item for item in measurements if item.metric == "bp_systolic" and item.unit.lower() == "mmhg"]
    diastolic = [item for item in measurements if item.metric == "bp_diastolic" and item.unit.lower() == "mmhg"]
    if systolic:
        results.append(_result("MEAN_SYSTOLIC", sum(item.value for item in systolic) / len(systolic), "mmHg", "mean(systolic_mmhg)", "wysh.synthetic.mean-v1", [item.measurement_id for item in systolic], "Descriptive aggregation only; no threshold classification."))
    if diastolic:
        results.append(_result("MEAN_DIASTOLIC", sum(item.value for item in diastolic) / len(diastolic), "mmHg", "mean(diastolic_mmhg)", "wysh.synthetic.mean-v1", [item.measurement_id for item in diastolic], "Descriptive aggregation only; no threshold classification."))
    by_time = {item.observed_at: item for item in systolic}
    pairs = [(by_time[item.observed_at], item) for item in diastolic if item.observed_at in by_time]
    if pairs:
        results.append(_result("MEAN_PULSE_PRESSURE", sum(sys.value - dia.value for sys, dia in pairs) / len(pairs), "mmHg", "mean(systolic_mmhg − diastolic_mmhg) over paired timestamps", "wysh.synthetic.mean-v1", [ref.measurement_id for pair in pairs for ref in pair], "Descriptive paired calculation only; no hemodynamic interpretation."))
    return results


def _ckd(request: CalculationRequest, measurements: list[LongitudinalMeasurement]) -> list[CalculationResult]:
    creatinine = _latest(measurements, "creatinine")
    if creatinine is None:
        return []
    if request.age_years is None or request.sex is None:
        return [_result("EGFR_CKD_EPI_2021", None, "mL/min/1.73 m²", "142 × min(SCr/κ,1)^α × max(SCr/κ,1)^−1.200 × 0.9938^Age × 1.012[if female]", NIDDK_EGFR_REFERENCE, [creatinine.measurement_id], "Age and sex are required; calculation abstained.", "ABSTAINED")]
    scr = creatinine.value
    kappa, alpha = (0.7, -0.241) if request.sex == "female" else (0.9, -0.302)
    egfr = 142 * pow(min(scr / kappa, 1), alpha) * pow(max(scr / kappa, 1), -1.2) * pow(0.9938, request.age_years) * (1.012 if request.sex == "female" else 1.0)
    return [_result("EGFR_CKD_EPI_2021", egfr, "mL/min/1.73 m²", "142 × min(SCr/κ,1)^α × max(SCr/κ,1)^−1.200 × 0.9938^Age × 1.012[if female]", NIDDK_EGFR_REFERENCE, [creatinine.measurement_id], "Single-point estimate only; standardized creatinine, longitudinal evidence, and clinician interpretation are required. It does not confirm chronic kidney disease or direct treatment.")]


def calculate(request: CalculationRequest) -> VerifiedCalculationResponse:
    normalized = normalize_measurements(request.measurements)
    invalid = next((item for item in normalized if not isfinite(item.value) or (item.metric in {"glucose", "hba1c", "bp_systolic", "bp_diastolic", "creatinine", "uacr", "urine_albumin"} and item.value <= 0)), None)
    if invalid is not None:
        input_hash = _input_hash(request, normalized)
        return VerifiedCalculationResponse(
            calculation_id=f"calculation-{request.disease_id}-{request.patient_id}", disease_id=request.disease_id,
            calculations=[_result("INVALID_NUMERIC_INPUT", None, None, "domain and finite-value validation", "wysh.synthetic.validation-v1", [invalid.measurement_id], "Calculation abstained because a supplied measurement is non-finite or outside the supported positive numeric domain.", "ABSTAINED")],
            abstained=True, rationale="Versioned synthetic calculation output only; invalid numeric input caused fail-closed abstention.", provenance=CalculationProvenance(input_hash=input_hash),
        )
    calculations = {"diabetes": _diabetes, "hypertension": _hypertension}.get(request.disease_id, lambda _items: _ckd(request, normalized) if request.disease_id == "chronic-kidney-disease" else [])(normalized)
    input_hash = _input_hash(request, normalized)
    return VerifiedCalculationResponse(
        calculation_id=f"calculation-{request.disease_id}-{request.patient_id}", disease_id=request.disease_id,
        calculations=calculations, abstained=not bool(calculations),
        rationale="Versioned synthetic calculation output only; no diagnosis, risk classification, treatment, prescription, referral, or record write was generated.",
        provenance=CalculationProvenance(input_hash=input_hash),
    )
