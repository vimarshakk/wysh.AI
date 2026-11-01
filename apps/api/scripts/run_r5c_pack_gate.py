"""Verify all 20 disease-specific contracts execute safely on synthetic observations."""

from __future__ import annotations

import json
from pathlib import Path

from app.disease_specific_intelligence import DiseaseSpecificRequest, evaluate, load_disease_specific_packs
from app.disease_intelligence import LongitudinalMeasurement


def main() -> int:
    root = Path(__file__).parents[3]
    packs = load_disease_specific_packs()
    per_pack: dict[str, bool] = {}
    for disease_id, pack in packs.items():
        measurements = [LongitudinalMeasurement(measurement_id=f"r5c-{disease_id}-{metric}", metric=metric, value=1.0, unit=pack.unit_allowlist.get(metric, ["score"])[0], observed_at="2026-10-01T00:00:00Z", source_type="observation") for metric in pack.required_metrics]
        result = evaluate(DiseaseSpecificRequest(tenant_id="synthetic-r5c-tenant", patient_id=f"synthetic-{disease_id}", disease_id=disease_id, measurements=measurements, synthetic=True))
        per_pack[disease_id] = result.status == "DATA_QUALITY_ONLY" and result.pack_version == "r5c-disease-specific-v1" and result.synthetic_only and not result.clinical_use_authorized
    payload = {"suite": "synthetic-r5c-disease-specific-pack-gate", "status": "PASS" if len(per_pack) == 20 and all(per_pack.values()) else "FAIL", "pack_count": len(per_pack), "per_pack": per_pack, "scope": "disease-specific-data-quality-and-descriptive-trends", "clinical_validation": "NO-GO", "synthetic_only": True}
    output = root / "artifacts/r5-test-evidence/r5c-pack-gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), **payload}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
