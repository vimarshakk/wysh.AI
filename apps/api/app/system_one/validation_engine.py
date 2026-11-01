"""System One validation engine: external validation, metrics, subgroup analysis.

Phase 2 prototype. Evaluates the System One decision model on held-out,
de-identified clinical data. Computes AUROC, AUPRC, Brier score, calibration
(ECE), and subgroup performance by language, comorbidity, age, and sex.

All validation is synthetic-only, deny-by-default, and fail-closed. No
clinical use authorization is implied by validation results.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ValidationCase:
    """Single validation case: model outputs + actual outcome."""
    case_id: str
    indication: str
    language: str
    age_band: str
    sex: str
    comorbidity_count: int
    noul_probability: float
    noul_confidence: float
    noul_abstained: bool
    choice_selected: str | None
    choice_confidence: float
    choice_abstained: bool
    actual_outcome: int  # 0 or 1
    choice_correct: bool | None  # 1 if choice matched actual, None if abstained


class NoulMetrics(BaseModel):
    auroc: float | None = Field(default=None, ge=0.0, le=1.0)
    auprc: float | None = Field(default=None, ge=0.0, le=1.0)
    brier_score: float | None = Field(default=None, ge=0.0, le=1.0)
    expected_calibration_error: float | None = Field(default=None, ge=0.0, le=1.0)
    n_labeled: int = Field(ge=0)
    n_abstained: int = Field(ge=0)
    n_human_handoff: int = Field(ge=0)
    status: Literal["VALID", "INSUFFICIENT_SAMPLE", "INVALID_DATA"] = "INSUFFICIENT_SAMPLE"


class ChoiceMetrics(BaseModel):
    accuracy: float | None = Field(default=None, ge=0.0, le=1.0)
    f1_score: float | None = Field(default=None, ge=0.0, le=1.0)
    n_evaluated: int = Field(ge=0)
    n_abstained: int = Field(ge=0)
    status: Literal["VALID", "INSUFFICIENT_SAMPLE", "INVALID_DATA"] = "INSUFFICIENT_SAMPLE"


class SubgroupSlice(BaseModel):
    dimension: str  # language, age_band, sex, comorbidity
    value: str
    n_cases: int
    noul_auroc: float | None = None
    choice_accuracy: float | None = None
    abstention_rate: float | None = None


class ValidationReport(BaseModel):
    report_id: str = Field(min_length=1, max_length=200)
    model_id: str = Field(min_length=1, max_length=200)
    indication: str = Field(min_length=1, max_length=100)
    dataset_id: str = Field(min_length=1, max_length=200)
    noul_metrics: NoulMetrics
    choice_metrics: ChoiceMetrics
    subgroup_slices: list[SubgroupSlice] = Field(default_factory=list)
    overall_abstention_rate: float = Field(ge=0.0, le=1.0)
    overall_human_handoff_rate: float = Field(ge=0.0, le=1.0)
    clinical_use_authorized: bool = False
    synthetic_only: bool = True
    validation_timestamp: str = Field(min_length=1, max_length=100)


class SystemOneValidationEngine:
    """Validates System One decision model outputs on held-out data."""

    def __init__(self, model_id: str, indication: str):
        self._model_id = model_id
        self._indication = indication
        self._cases: list[ValidationCase] = []

    def add_case(self, case: ValidationCase) -> None:
        if case.indication != self._indication:
            raise ValidationError(f"case indication {case.indication} != engine indication {self._indication}")
        self._cases.append(case)

    def _sigmoid(self, value: float) -> float:
        value = max(-40.0, min(40.0, value))
        return 1.0 / (1.0 + exp(-value))

    def _auroc(self, probabilities: list[float], labels: list[int]) -> float | None:
        """Compute AUROC via Mann-Whitney U statistic."""
        if len(probabilities) != len(labels) or not probabilities:
            return None
        if len(set(labels)) < 2:
            return None
        pairs = [(probabilities[i], labels[i]) for i in range(len(probabilities))]
        positives = [p for p, l in pairs if l == 1]
        negatives = [p for p, l in pairs if l == 0]
        if not positives or not negatives:
            return None
        concordant = 0
        total = 0
        for p_pos in positives:
            for p_neg in negatives:
                total += 1
                if p_pos > p_neg:
                    concordant += 1
                elif p_pos == p_neg:
                    concordant += 0.5
        return concordant / total if total > 0 else None

    def _auprc(self, probabilities: list[float], labels: list[int]) -> float | None:
        """Compute AUPRC via precision-recall curve trapezoidal integration."""
        if len(probabilities) != len(labels) or not probabilities:
            return None
        if len(set(labels)) < 2:
            return None
        # Sort by probability descending
        sorted_pairs = sorted(zip(probabilities, labels), key=lambda x: -x[0])
        total_positives = sum(labels)
        if total_positives == 0:
            return None
        tp = 0
        fp = 0
        prev_recall = 0.0
        prev_precision = 1.0
        area = 0.0
        for prob, label in sorted_pairs:
            if label == 1:
                tp += 1
            else:
                fp += 1
            recall = tp / total_positives
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            area += (recall - prev_recall) * ((prev_precision + precision) / 2.0)
            prev_recall = recall
            prev_precision = precision
        return area

    def _brier_score(self, probabilities: list[float], labels: list[int]) -> float | None:
        if len(probabilities) != len(labels) or not probabilities:
            return None
        return sum((p - l) ** 2 for p, l in zip(probabilities, labels)) / len(labels)

    def _ece(self, probabilities: list[float], labels: list[int], n_bins: int = 10) -> float | None:
        """Expected Calibration Error."""
        if len(probabilities) != len(labels) or not probabilities:
            return None
        bin_boundaries = [i / n_bins for i in range(n_bins + 1)]
        ece = 0.0
        total = len(probabilities)
        for i in range(n_bins):
            bin_low = bin_boundaries[i]
            bin_high = bin_boundaries[i + 1]
            bin_indices = [
                j for j in range(total)
                if bin_low <= probabilities[j] < bin_high
                or (i == n_bins - 1 and probabilities[j] <= bin_high)
            ]
            if not bin_indices:
                continue
            bin_accuracy = sum(labels[j] for j in bin_indices) / len(bin_indices)
            bin_confidence = sum(probabilities[j] for j in bin_indices) / len(bin_indices)
            bin_weight = len(bin_indices) / total
            ece += bin_weight * abs(bin_confidence - bin_accuracy)
        return ece

    def _subgroup_slices(self) -> list[SubgroupSlice]:
        """Compute subgroup performance slices by language, age_band, sex, comorbidity."""
        slices: list[SubgroupSlice] = []
        dimensions: dict[str, list[str]] = {
            "language": sorted({c.language for c in self._cases}),
            "age_band": sorted({c.age_band for c in self._cases}),
            "sex": sorted({c.sex for c in self._cases}),
            "comorbidity_count": sorted({str(c.comorbidity_count) for c in self._cases}),
        }
        for dimension, values in dimensions.items():
            for value in values:
                subset = [c for c in self._cases if self._dim_value(c, dimension) == value]
                if not subset:
                    continue
                noul_probs = [c.noul_probability for c in subset if not c.noul_abstained]
                noul_labels = [c.actual_outcome for c in subset if not c.noul_abstained]
                choice_evaluated = [c for c in subset if not c.choice_abstained and c.choice_correct is not None]
                n_cases = len(subset)
                n_abstained = sum(1 for c in subset if c.noul_abstained or c.choice_abstained)
                slices.append(SubgroupSlice(
                    dimension=dimension,
                    value=value,
                    n_cases=n_cases,
                    noul_auroc=self._auroc(noul_probs, noul_labels) if noul_probs else None,
                    choice_accuracy=(
                        sum(1 for c in choice_evaluated if c.choice_correct) / len(choice_evaluated)
                        if choice_evaluated else None
                    ),
                    abstention_rate=round(n_abstained / n_cases, 6) if n_cases > 0 else 0.0,
                ))
        return slices

    @staticmethod
    def _dim_value(case: ValidationCase, dimension: str) -> str:
        if dimension == "language":
            return case.language
        if dimension == "age_band":
            return case.age_band
        if dimension == "sex":
            return case.sex
        if dimension == "comorbidity_count":
            return case.comorbidity_count
        return ""

    def generate_report(self, dataset_id: str) -> ValidationReport:
        """Generate the full validation report."""
        if not self._cases:
            raise ValidationError("no validation cases have been added")

        # Noul metrics
        noul_probs = [c.noul_probability for c in self._cases if not c.noul_abstained]
        noul_labels = [c.actual_outcome for c in self._cases if not c.noul_abstained]
        noul_metrics = NoulMetrics(
            auroc=self._auroc(noul_probs, noul_labels) if noul_probs else None,
            auprc=self._auprc(noul_probs, noul_labels) if noul_probs else None,
            brier_score=self._brier_score(noul_probs, noul_labels) if noul_probs else None,
            expected_calibration_error=self._ece(noul_probs, noul_labels) if noul_probs else None,
            n_labeled=len(noul_probs),
            n_abstained=sum(1 for c in self._cases if c.noul_abstained),
            n_human_handoff=sum(1 for c in self._cases if c.noul_abstained),
        )
        if noul_metrics.n_labeled < 30 or (noul_probs and len(set(noul_labels)) < 2):
            noul_metrics.status = "INSUFFICIENT_SAMPLE"
        elif noul_probs:
            noul_metrics.status = "VALID"

        # Choice metrics
        choice_evaluated = [c for c in self._cases if not c.choice_abstained and c.choice_correct is not None]
        choice_correct_count = sum(1 for c in choice_evaluated if c.choice_correct)
        choice_metrics = ChoiceMetrics(
            accuracy=(choice_correct_count / len(choice_evaluated)) if choice_evaluated else None,
            f1_score=None,  # requires per-class computation; placeholder
            n_evaluated=len(choice_evaluated),
            n_abstained=sum(1 for c in self._cases if c.choice_abstained),
        )
        if choice_metrics.n_evaluated < 30:
            choice_metrics.status = "INSUFFICIENT_SAMPLE"
        elif choice_metrics.n_evaluated > 0:
            choice_metrics.status = "VALID"

        overall_abstention = sum(1 for c in self._cases if c.noul_abstained or c.choice_abstained) / len(self._cases)
        overall_handoff = sum(1 for c in self._cases if c.noul_abstained) / len(self._cases)

        return ValidationReport(
            report_id=f"validation-{self._model_id}-{self._indication}",
            model_id=self._model_id,
            indication=self._indication,
            dataset_id=dataset_id,
            noul_metrics=noul_metrics,
            choice_metrics=choice_metrics,
            subgroup_slices=self._subgroup_slices(),
            overall_abstention_rate=round(overall_abstention, 6),
            overall_human_handoff_rate=round(overall_handoff, 6),
            clinical_use_authorized=False,
            synthetic_only=True,
            validation_timestamp=self._utc_now(),
        )

    @staticmethod
    def _utc_now() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def public_status(self) -> dict[str, object]:
        return {
            "model_id": self._model_id,
            "indication": self._indication,
            "n_cases": len(self._cases),
            "synthetic_only": True,
            "clinical_use_authorized": False,
            "deny_by_default": True,
        }
