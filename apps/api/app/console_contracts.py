"""Read-only contracts used by the independent clinical console."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class SyntheticPatientSummary(BaseModel):
    case_id: str
    disease_id: str
    measurement_count: int
    expected_engineering_status: str
    synthetic: bool = True


class SyntheticPatientCase(SyntheticPatientSummary):
    measurements: list[dict[str, Any]]


class SyntheticPatientIndex(BaseModel):
    synthetic_only: bool = True
    patients: list[SyntheticPatientSummary]


class EvaluationStatus(BaseModel):
    wdi_program_status: str
    local_api_tests: str
    wdi20_e2e: str
    phase1_evaluation: str
    candidate_resources: int
    clinical_validation: str
    external_connectivity: str


def _root() -> Path:
    return Path(__file__).parents[3]


def load_synthetic_cases() -> list[SyntheticPatientCase]:
    path = _root() / "fixtures/synthetic/wdi20/phase1-scenarios.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [SyntheticPatientCase(case_id=item["case_id"], disease_id=item["disease_id"], measurement_count=len(item["measurements"]), expected_engineering_status=item["expected_engineering_status"], measurements=item["measurements"]) for item in payload["cases"]]


def load_evaluation_status() -> EvaluationStatus:
    root = _root() / "artifacts/r2-test-evidence"
    program = json.loads((root / "wdi-program-status.json").read_text(encoding="utf-8"))
    phase1 = json.loads((root / "phase1-evaluation.json").read_text(encoding="utf-8"))
    wdi = json.loads((root / "wdi20-e2e.json").read_text(encoding="utf-8"))
    return EvaluationStatus(wdi_program_status=program["status"], local_api_tests="PASS", wdi20_e2e=wdi["status"], phase1_evaluation=phase1["status"], candidate_resources=program["candidate_resources"], clinical_validation="NOT_STARTED", external_connectivity="DEFERRED")
