"""De-identification gate for wysh.AI training data pipeline.

Phase 0 scaffold. Enforces that no PHI or real patient identifiers enter the
repository training datasets. Runs as a pre-commit / pre-training gate.

Usage:
    python apps/api/scripts/deidentify.py --path research/datasets/staging/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PHI_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "ssn"),
    (re.compile(r"\b\d{10}\b"), "phone_or_mrn_like"),
    (re.compile(r"\b\d{12}\b"), "aadhaar_like"),
    (re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"), "email"),
]

PROHIBITED_CONTEXT_KEYS = {
    "name", "full_name", "email", "phone", "mobile", "address", "dob",
    "date_of_birth", "aadhaar", "mrn", "medical_record_number", "ssn",
    "free_text", "document",
}


def contains_phi(text: str) -> bool:
    return any(pattern.search(text or "") for pattern, _ in PHI_PATTERNS)


def validate_record(record: dict) -> list[str]:
    errors: list[str] = []

    for field in ("tenant_id", "patient_id"):
        value = record.get(field, "")
        if not isinstance(value, str) or not value.startswith("synthetic-"):
            errors.append(f"{field} must be a synthetic identifier")

    serialized = json.dumps(record, sort_keys=True)
    for pattern, classification in PHI_PATTERNS:
        if pattern.search(serialized):
            errors.append(f"PHI pattern detected: {classification}")

    context = record.get("context", {})
    if isinstance(context, dict):
        for key in context:
            if key.lower() in PROHIBITED_CONTEXT_KEYS:
                errors.append(f"prohibited context key: {key}")

    if record.get("synthetic") is not True:
        errors.append("synthetic flag must be true")

    return errors


def validate_directory(path: Path) -> int:
    total = 0
    failed = 0
    for jsonl_file in sorted(path.rglob("*.jsonl")):
        with jsonl_file.open("r", encoding="utf-8", errors="ignore") as fh:
            for line_number, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                total += 1
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    print(f"{jsonl_file}:{line_number}: invalid JSON")
                    failed += 1
                    continue
                errors = validate_record(record)
                if errors:
                    failed += 1
                    for err in errors:
                        print(f"{jsonl_file}:{line_number}: {err}")
    print(f"Validated {total} records; {failed} failed de-identification gate")
    return failed


def main() -> None:
    parser = argparse.ArgumentParser(description="De-identification gate for training data")
    parser.add_argument("--path", required=True, help="Directory of JSONL files to validate")
    args = parser.parse_args()
    path = Path(args.path)
    if not path.is_dir():
        print(f"Directory not found: {path}")
        sys.exit(2)
    failed = validate_directory(path)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
