"""Validate WDI-20 program scaffolding without implying clinical completion."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).parents[3]


def main() -> int:
    catalog = json.loads((ROOT / "disease-intelligence/registry/disease-catalog.json").read_text())
    conditions = {item["id"] for item in catalog["conditions"]}
    with (ROOT / "research/open-source-catalog.csv").open(newline="", encoding="utf-8") as handle:
        resources = list(csv.DictReader(handle))
    matrix_lines = (ROOT / "research/disease-resource-matrix.md").read_text(encoding="utf-8").splitlines()
    matrix_rows = [line for line in matrix_lines if line.startswith("| ") and "WDI condition" not in line and "---" not in line]
    matrix_conditions = {row.split("|")[1].strip() for row in matrix_rows}
    required = [
        "docs/wdi-20/00-repository-baseline.md",
        "docs/wdi-20/01-capability-inventory.md",
        "docs/wdi-20/02-integration-boundaries.md",
        "docs/wdi-20/03-existing-assets-reuse-plan.md",
        "docs/wdi-20/PROGRAM_CHECKLIST.md",
        "research/open-source-catalog.csv",
        "research/disease-resource-matrix.md",
        "research/india-global-burden-20.md",
        "research/disease-priority-scorecard.csv",
        "research/epidemiology-sources.json",
        "research/india-specific-clinical-gaps.md",
    ]
    checks = {
        "catalog_has_20_conditions": len(conditions) == 20,
        "candidate_register_has_at_least_40_rows": len(resources) >= 40,
        "matrix_has_20_rows": len(matrix_rows) == 20,
        "matrix_matches_catalog": matrix_conditions == conditions,
        "required_artifacts_present": all((ROOT / path).exists() for path in required),
        "runtime_claims_not_promoted": all(row.get("verification_state", "").startswith("CANDIDATE") or row.get("verification_state", "").startswith("VERIFIED") for row in resources),
    }
    payload = {
        "suite": "wdi-20-program-scaffold-gate",
        "status": "IN_PROGRESS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "catalog_conditions": len(conditions),
        "candidate_resources": len(resources),
        "matrix_rows": len(matrix_rows),
        "clinical_validation_complete": False,
        "training_pipeline_complete": False,
        "external_connectivity_verified": False,
        "note": "Structural program scaffold only; not a clinical or release gate.",
    }
    output = ROOT / "artifacts/r2-test-evidence/wdi-program-status.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), **payload}, indent=2))
    return 0 if payload["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
