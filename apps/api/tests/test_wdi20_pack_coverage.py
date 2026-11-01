import json
from pathlib import Path

from app.clinical_engine import ClinicalAssessmentRequest, assess, load_phase1_packs
from app.disease_intelligence import LongitudinalMeasurement


def test_all_catalog_conditions_have_independently_executable_data_quality_packs():
    root = Path(__file__).parents[3]
    catalog = json.loads((root / "disease-intelligence/registry/disease-catalog.json").read_text())
    catalog_ids = {item["id"] for item in catalog["conditions"]}
    packs = load_phase1_packs()
    assert set(packs) == catalog_ids
    for disease_id, pack in packs.items():
        measurements = [LongitudinalMeasurement(measurement_id=f"{disease_id}-{metric}", metric=metric, value=1.0, unit="synthetic", observed_at="2026-10-01T00:00:00Z", source_type="observation") for metric in pack.required_for_review]
        result = assess(ClinicalAssessmentRequest(tenant_id="synthetic-wdi20-tenant", patient_id=f"synthetic-{disease_id}", disease_id=disease_id, measurements=measurements, synthetic=True))
        assert result.abstained is False, disease_id
        assert result.pack_version == pack.pack_version
        assert result.provenance.synthetic_only is True
        assert result.clinical_use_authorized is False
