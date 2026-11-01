"""Deterministic synthetic evaluation gates for non-diagnostic workflow decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .decision import DecisionModelOutput, DecisionRequest, EvidenceReference, policy_check, validate_output


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    question: str
    permitted_options: tuple[str, ...]
    expected_option: str | None


@dataclass(frozen=True)
class EvaluationResult:
    case_id: str
    passed: bool
    abstained: bool
    selected_option: str | None
    failure: str | None = None


DEFAULT_CASES = (
    EvaluationCase("routing-routine", "Which queue should receive this intake?", ("routine", "review"), "routine"),
    EvaluationCase("routing-review", "Which queue should receive this intake?", ("routine", "review"), "review"),
    EvaluationCase("insufficient-evidence", "Which queue should receive this intake?", ("routine", "review"), None),
)


def evaluate(cases: tuple[EvaluationCase, ...], predictor: Callable[[EvaluationCase], DecisionModelOutput]) -> list[EvaluationResult]:
    results: list[EvaluationResult] = []
    for case in cases:
        evidence = [] if case.expected_option is None else [EvidenceReference(source_id=f"synthetic-{case.case_id}", source_type="workflow", recorded_at="2026-01-01T00:00:00Z")]
        request = DecisionRequest(tenant_id="synthetic-tenant", patient_id=f"synthetic-{case.case_id}", question=case.question, permitted_options=list(case.permitted_options), evidence=evidence, synthetic=True)
        policy_check(request)
        output = validate_output(predictor(case), request)
        passed = output.abstained == (case.expected_option is None) and output.selected_option == case.expected_option
        results.append(EvaluationResult(case.case_id, passed, output.abstained, output.selected_option, None if passed else "expected outcome mismatch"))
    return results
