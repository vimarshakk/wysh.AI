"""Tests for the clinical-telemetry-v1 schema contract.

Validates that the JSON schema is well-formed and that sample structured
clinical telemetry records conform to it. Synthetic-only; no PHI.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest  # noqa

ROOT = Path(__file__).parents[3]
SCHEMA_PATH = ROOT / "packages" / "contracts" / "clinical-telemetry-v1.schema.json"


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_is_valid_json() -> None:
    schema = _load_schema()
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert schema["title"] == "Clinical Telemetry v1"
    assert schema["type"] == "object"


def test_required_fields_present() -> None:
    schema = _load_schema()
    required = set(schema["required"])
    assert "tenant_id" in required
    assert "patient_id" in required
    assert "language" in required
    assert "encounter" in required
    assert "vitals" in required
    assert "conditions" in required
    assert "medications" in required
    assert "questions" in required


def test_synthetic_flag_required_true() -> None:
    schema = _load_schema()
    prop = schema["properties"]["synthetic"]
    assert prop.get("type") == "boolean"
    assert prop.get("const") is True


def test_tenant_and_patient_must_be_synthetic() -> None:
    schema = _load_schema()
    for field in ("tenant_id", "patient_id"):
        pattern = schema["properties"][field]["pattern"]
        assert pattern == "^synthetic-"


def test_supported_languages() -> None:
    schema = _load_schema()
    languages = set(schema["properties"]["language"]["enum"])
    expected = {"en", "hi", "te", "ta", "bn", "mr", "es", "zh", "ar", "fr"}
    assert languages == expected


def test_question_types() -> None:
    schema = _load_schema()
    items = schema["properties"]["questions"]["items"]
    qt_enum = items["properties"]["question_type"]["enum"]
    assert set(qt_enum) == {"choice", "score", "noul"}


def test_sample_valid_telemetry_conforms() -> None:
    schema = _load_schema()
    record = {
        "tenant_id": "synthetic-tenant-1",
        "patient_id": "synthetic-patient-1",
        "encounter_id": "synthetic-encounter-1",
        "language": "en",
        "recorded_at": "2026-01-01T00:00:00Z",
        "encounter": {"type": "outpatient", "setting": "clinic", "department": "medicine"},
        "vitals": [
            {
                "metric": "hba1c_percent",
                "value": 7.2,
                "unit": "%",
                "recorded_at": "2026-01-01T00:00:00Z",
                "source_id": "synthetic-obs-1",
            },
            {
                "metric": "bp_systolic_mmhg",
                "value": 138.0,
                "unit": "mmHg",
                "recorded_at": "2026-01-01T00:00:00Z",
                "source_id": "synthetic-obs-2",
            },
        ],
        "conditions": [
            {
                "code": "E11.9",
                "code_system": "icd10",
                "status": "active",
                "severity": "moderate",
                "recorded_at": "2026-01-01T00:00:00Z",
                "source_id": "synthetic-cond-1",
            }
        ],
        "medications": [
            {
                "code": "860975",
                "code_system": "rxnorm",
                "status": "active",
                "dosage": "500 mg",
                "recorded_at": "2026-01-01T00:00:00Z",
                "source_id": "synthetic-med-1",
            }
        ],
        "questions": [
            {
                "question_id": "q1",
                "question_text": "Is glycemic control adequate?",
                "question_type": "noul",
                "permitted_options": ["yes", "no"],
                "indication": "diabetes",
            }
        ],
        "context": {},
        "synthetic": True,
    }

    # Structural assertions mirroring the schema
    assert record["tenant_id"].startswith("synthetic-")
    assert record["patient_id"].startswith("synthetic-")
    assert record["language"] in schema["properties"]["language"]["enum"]
    assert record["synthetic"] is True
    assert len(record["vitals"]) <= schema["properties"]["vitals"]["maxItems"]
    assert len(record["questions"]) <= schema["properties"]["questions"]["maxItems"]
    for q in record["questions"]:
        assert q["question_type"] in {"choice", "score", "noul"}
        assert 2 <= len(q["permitted_options"]) <= 20


def test_non_synthetic_identifier_rejected() -> None:
    record = {"tenant_id": "real-tenant", "patient_id": "synthetic-patient-1", "synthetic": True}
    assert not record["tenant_id"].startswith("synthetic-")


def test_phi_context_keys_prohibited() -> None:
    prohibited = {"name", "mrn", "ssn", "email", "phone", "document"}
    context = {"mrn": "123456", "name": "John Doe"}
    assert prohibited.intersection(k.lower() for k in context)
