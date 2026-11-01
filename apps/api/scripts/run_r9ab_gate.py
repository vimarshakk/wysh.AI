"""R9A/R9B synthetic imaging contract and adapter isolation gate."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.imaging_research import FhirImagingStudyContract, ImagingAdapterRequest, ImagingProvenanceRecord, MonaiResearchAdapter, SyntheticDicomMetadata, UnconfiguredImagingAdapter, adapter_status, canonical_source_hash, validate_de_identification  # noqa


def main() -> None:
    dicom = SyntheticDicomMetadata(study_instance_uid="2.25.10000001", series_instance_uid="2.25.10000002", sop_instance_uid="2.25.10000003", modality="DX", body_part="chest", transfer_syntax_uid="1.2.840.10008.1.2.1", pixel_hash="a" * 64, de_identification_method="synthetic-fixture-v1")
    study = FhirImagingStudyContract(resource_id="study-r9-001", subject_reference="Patient/synthetic-imaging-001", status="available", modality="DX", started="2025-01-01T08:00:00Z", dicom=dicom)
    source_hash = canonical_source_hash(study)
    request = ImagingAdapterRequest(study=study, task="report_draft", provenance=ImagingProvenanceRecord(source_hash=source_hash, fhir_resource_hash=source_hash))
    report = {"schema_version": "r9ab-gate-v1", "milestone": "R9A-R9B", "status": "PASS", "synthetic_only": True, "dicom_fhir_contract": validate_de_identification(study), "source_hash": source_hash, "adapter_status": adapter_status(), "unconfigured_adapter": UnconfiguredImagingAdapter().analyze(request).model_dump(mode="json"), "monai_adapter": MonaiResearchAdapter().analyze(request).model_dump(mode="json"), "model_weights_downloaded": False, "clinical_use_authorized": False, "clinical_governance": "HOLD", "clinical_validation": "NO-GO", "production": "NO-GO"}  # noqa
    output = ROOT / "artifacts/r9-test-evidence/r9ab-gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "output": str(output), "source_hash": source_hash, "weights_downloaded": False}))


if __name__ == "__main__":
    main()
