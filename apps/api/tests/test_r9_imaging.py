from __future__ import annotations

import pytest

from app.imaging_research import FhirImagingStudyContract, ImagingAdapterRequest, ImagingProvenanceRecord, MonaiResearchAdapter, SyntheticDicomMetadata, UnconfiguredImagingAdapter, adapter_status, canonical_source_hash, validate_de_identification


def synthetic_study() -> FhirImagingStudyContract:
    dicom = SyntheticDicomMetadata(study_instance_uid="2.25.10000001", series_instance_uid="2.25.10000002", sop_instance_uid="2.25.10000003", modality="DX", body_part="chest", transfer_syntax_uid="1.2.840.10008.1.2.1", pixel_hash="a" * 64, de_identification_method="synthetic-fixture-v1")
    return FhirImagingStudyContract(resource_id="study-r9-001", subject_reference="Patient/synthetic-imaging-001", status="available", modality="DX", started="2025-01-01T08:00:00Z", dicom=dicom)


def test_synthetic_dicom_fhir_contract_has_provenance_and_deidentification_gate():
    study = synthetic_study()
    result = validate_de_identification(study)
    assert result["status"] == "PASS"
    assert len(canonical_source_hash(study)) == 64


def test_non_synthetic_contract_is_rejected():
    with pytest.raises(ValueError):
        SyntheticDicomMetadata(study_instance_uid="2.25.10000001", series_instance_uid="2.25.10000002", sop_instance_uid="2.25.10000003", modality="DX", body_part="chest", transfer_syntax_uid="1.2.840.10008.1.2.1", pixel_hash="a" * 64, de_identification_method="fixture", synthetic=False)


def test_adapters_are_isolated_and_abstaining_without_approved_weights():
    request = ImagingAdapterRequest(study=synthetic_study(), task="report_draft", provenance=ImagingProvenanceRecord(source_hash="b" * 64, fhir_resource_hash="c" * 64))
    assert UnconfiguredImagingAdapter().analyze(request).status == "ABSTAINED"
    assert MonaiResearchAdapter().analyze(request).clinical_use_authorized is False
    assert all(item["model_execution"] == "ABSTAIN" for item in adapter_status())
