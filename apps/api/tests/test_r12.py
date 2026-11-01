from __future__ import annotations

import pytest

from app.imaging_infrastructure import ImagingPrototypeManifest, LocalImagingServiceConfig, prototype_status, resource_gate
from app.interop_adapters import AuthorizationParityCase, HapiConformanceContract, TerminologyServiceContract, evaluate_authorization_parity
from app.research_evaluation import INSUFFICIENT_SAMPLE, evaluation_readiness


def test_r12a_evaluation_readiness_with_small_cohort_does_not_claim_validity():
    report = evaluation_readiness(labels=[0, 1] * 10, probabilities=[0.1, 0.9] * 10, subgroup_values=["A", "B"] * 10)
    assert report["sample_adequacy"]["status"] == INSUFFICIENT_SAMPLE
    assert report["subgroup_adequacy"]["status"] == INSUFFICIENT_SAMPLE
    assert report["external_validation_readiness"].startswith("READY_ONLY_AFTER")


def test_r12b_imaging_prototypes_are_local_and_resource_bounded():
    manifest = ImagingPrototypeManifest()
    assert all(item["model_execution"] == "ABSTAIN" for item in prototype_status(manifest))
    assert resource_gate(width=1000, height=1000, timeout_ms=5000)["status"] == "PASS"
    assert resource_gate(width=100000, height=100000, timeout_ms=5000)["status"] == "ABSTAINED"
    with pytest.raises(ValueError):
        LocalImagingServiceConfig(service="orthanc", base_url="https://public.example")


def test_r12c_authorization_parity_and_fhir_contracts_are_explicit():
    cases = [AuthorizationParityCase(case_id="allow-clinician", tenant_id="t", patient_id="p", relation="clinician", canonical_allowed=True, candidate_allowed=True), AuthorizationParityCase(case_id="revoked", tenant_id="t", patient_id="p", relation="caregiver", canonical_allowed=False, candidate_allowed=False, revoked=True)]
    assert evaluate_authorization_parity(cases)["status"] == "PASS"
    assert HapiConformanceContract(required_resources=["Bundle", "Patient", "Observation", "Consent"]).external_server_enabled is False
    assert TerminologyServiceContract(terminology_version="synthetic-terminology-v1", code_systems=["http://loinc.org"]).distribution_rights_reviewed is False


def test_r12c_detects_candidate_authorization_mismatch():
    case = AuthorizationParityCase(case_id="mismatch", tenant_id="t", patient_id="p", relation="none", canonical_allowed=False, candidate_allowed=True)
    assert evaluate_authorization_parity([case])["status"] == "FAIL"
