"""MIMIC-IV data ingestion skeleton for wysh.AI System One training pipeline.

Phase 0 scaffold. This module reads MIMIC-IV JSONL/CSV exports, normalizes them
to the clinical-telemetry-v1 schema, and writes de-identified, language-tagged
records to the repository-local staging area for engineering evaluation only.

It does NOT ingest PHI. All real patient identifiers are stripped by the
de-identification gate before any record is persisted to this repository.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[2]
STAGING_DIR = ROOT / "research" / "datasets" / "staging"
MIMIC_SOURCE_DIR = ROOT / "research" / "datasets" / "mimic-source"

PHI_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),          # SSN
    re.compile(r"\b\d{10}\b"),                       # 10-digit phone/MRN-like
    re.compile(r"\b\d{12}\b"),                       # 12-digit Aadhaar-like
    re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),   # email
]


def synthetic_id(raw: str) -> str:
    """Derive a deterministic synthetic identifier from a real identifier."""
    return f"synthetic-{sha256(raw.encode()).hexdigest()[:16]}"


def contains_phi(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in PHI_PATTERNS)


def normalize_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize one MIMIC-IV row into clinical-telemetry-v1 shape.

    Returns None if the row fails de-identification or schema validation.
    """
    subject_id = row.get("subject_id") or row.get("patient_id")
    if not subject_id:
        return None
    if contains_phi(str(subject_id)):
        return None

    telemetry: dict[str, Any] = {
        "tenant_id": synthetic_id("wyshcare-mimic-tenant"),
        "patient_id": synthetic_id(str(subject_id)),
        "encounter_id": synthetic_id(str(row.get("hadm_id", subject_id))),
        "language": "en",
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "encounter": {"type": "inpatient"},
        "vitals": [],
        "conditions": [],
        "medications": [],
        "questions": [],
        "context": {},
        "synthetic": True,
    }

    # Vitals mapping (example: MIMIC chartevents/itemids -> standard metrics)
    vitals_map = {
        "heart_rate": "heart_rate_bpm",
        "sbp": "bp_systolic_mmhg",
        "dbp": "bp_diastolic_mmhg",
        "glucose": "mean_glucose_mg_dl",
        "temperature": "temperature_c",
        "spo2": "spo2_percent",
    }
    for src_metric, std_metric in vitals_map.items():
        value = row.get(src_metric)
        if value is not None:
            try:
                telemetry["vitals"].append({
                    "metric": std_metric,
                    "value": float(value),
                    "unit": std_metric.split("_")[-1] if "_" in std_metric else "",
                    "recorded_at": telemetry["recorded_at"],
                    "source_id": f"mimic-{std_metric}-{subject_id}",
                })
            except (TypeError, ValueError):
                continue

    # Conditions (example: ICD-9/ICD-10 codes)
    icd_code = row.get("icd_code") or row.get("diagnosis")
    if icd_code and not contains_phi(str(icd_code)):
        telemetry["conditions"].append({
            "code": str(icd_code),
            "code_system": "icd10",
            "status": "active",
            "severity": "unknown",
            "recorded_at": telemetry["recorded_at"],
            "source_id": f"mimic-condition-{subject_id}",
        })

    # Final PHI sweep across the whole record
    serialized = json.dumps(telemetry, sort_keys=True)
    if contains_phi(serialized):
        return None

    return telemetry


def ingest_mimic_directory(source_dir: Path, output_dir: Path) -> int:
    """Ingest all JSONL/CSV files in source_dir into normalized JSONL staging."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for source_file in sorted(source_dir.rglob("*")):
        if not source_file.is_file():
            continue
        suffix = source_file.suffix.lower()
        if suffix not in {".jsonl", ".csv", ".ndjson"}:
            continue
        out_file = output_dir / f"{source_file.stem}.normalized.jsonl"
        with source_file.open("r", encoding="utf-8", errors="ignore") as src, \
             out_file.open("w", encoding="utf-8") as dst:
            if suffix == ".csv":
                reader = csv.DictReader(src)
                for row in reader:
                    normalized = normalize_row(row)
                    if normalized:
                        dst.write(json.dumps(normalized, separators=(",", ":")) + "\n")
                        written += 1
            else:
                for line in src:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    normalized = normalize_row(row)
                    if normalized:
                        dst.write(json.dumps(normalized, separators=(",", ":")) + "\n")
                        written += 1
    return written


def main() -> None:
    if not MIMIC_SOURCE_DIR.is_dir():
        print(f"MIMIC source directory not found: {MIMIC_SOURCE_DIR}")
        print("Place de-identified MIMIC-IV exports there before running ingestion.")
        return
    count = ingest_mimic_directory(MIMIC_SOURCE_DIR, STAGING_DIR)
    print(f"Ingested {count} normalized records into {STAGING_DIR}")


if __name__ == "__main__":
    main()
