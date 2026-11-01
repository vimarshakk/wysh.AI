"""Verify that all WDI-20 conditions have executable synthetic data-quality packs."""

from __future__ import annotations

import json
from pathlib import Path

from app.clinical_engine import ClinicalAssessmentRequest, assess, load_phase1_packs
from app.disease_intelligence import LongitudinalMeasurement


def main() -> int:
    root = Path(__file__).parents[3]
    catalog = json.loads((root / "disease-intelligence/registry/disease-catalog.json").read_text())
    catalog_ids = {item["id"] for item in catalog["conditions"]}
    packs = load_phase1_packs()
    checks: dict[str, bool] = {"catalog_has_20_conditions": len(catalog_ids) == 20, "pack_registry_has_20_conditions": len(packs) == 20, "pack_ids_match_catalog": set(packs) == catalog_ids}
    per_pack: dict[str, bool] = {}
    for disease_id, pack in packs.items():
        measurements = [LongitudinalMeasurement(measurement_id=f"{disease_id}-{metric}", metric=metric, value=1.0, unit="synthetic", observed_at="2026-10-01T00:00:00Z", source_type="observation") for metric in pack.required_for_review]
        result = assess(ClinicalAssessmentRequest(tenant_id="synthetic-r5b-tenant", patient_id=f"synthetic-{disease_id}", disease_id=disease_id, measurements=measurements, synthetic=True))
        per_pack[disease_id] = result.abstained is False and result.clinical_use_authorized is False and result.provenance.synthetic_only is True
    checks["every_pack_executable"] = all(per_pack.values())
    payload = {"suite": "synthetic-r5b-pack-coverage", "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "pack_count": len(packs), "per_pack": per_pack, "scope": "data-quality-only", "clinical_validation": "NO-GO", "synthetic_only": True}
    output = root / "artifacts/r5-test-evidence/r5b-pack-coverage.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), **payload}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
