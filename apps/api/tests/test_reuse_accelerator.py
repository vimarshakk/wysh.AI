from fastapi.testclient import TestClient
import json
from pathlib import Path

from app.config import Settings
from app.main import create_app
from app.reuse_accelerator import CdsPathwayRequest, CqlExecutionRequest, NocturneIngestRequest, evaluate_cds_pathway, execute_cql_contract, ingest_nocturne
from app.standards_cql import StandardsCqlRequest, execute_fhir_elm_subset
from app.upstream_cql_runtime import execute_pinned_runtime
from app.terminology import TerminologyValidationRequest, validate_code


def test_nocturne_compatible_adapter_is_descriptive_and_does_not_claim_tir():
    result = ingest_nocturne(NocturneIngestRequest(tenant_id="synthetic-t", patient_id="synthetic-p", synthetic=True, entries=[{"entry_id":"e1", "value":120, "unit":"mg/dL", "observed_at":"2026-10-01T00:00:00Z"}]))
    assert result.analytics["status"] == "DESCRIPTIVE_ONLY"
    assert result.analytics["range_status"] == "NOT_CONFIGURED"
    assert result.clinical_use_authorized is False


def test_snomed_adapter_is_contract_only_without_vendored_pathway():
    result = evaluate_cds_pathway(CdsPathwayRequest(tenant_id="synthetic-t", patient_id="synthetic-p", pathway_id="diabetes-demo", synthetic=True))
    assert result.status == "CONTRACT_ONLY"
    assert result.notifications == []
    assert "not executed" in result.reason


def test_ahrq_style_cql_adapter_abstains_without_configured_runtime():
    result = execute_cql_contract(CqlExecutionRequest(tenant_id="synthetic-t", patient_id="synthetic-p", library_id="demo", expression_id="demo", synthetic=True, facts=[{"id":"f1"}]))
    assert result.status == "UNCONFIGURED"
    assert result.result is None
    assert len(result.facts_hash) == 64


def test_bounded_cql_subset_executes_only_allowlisted_synthetic_expressions():
    result = execute_cql_contract(CqlExecutionRequest(tenant_id="synthetic-t", patient_id="synthetic-p", library_id="wysh.synthetic.rules.v1", expression_id="mean-numeric", synthetic=True, facts=[{"id": "g1", "metric": "glucose", "value": 100}, {"id": "g2", "metric": "glucose", "value": 140}]))
    assert result.status == "EXECUTED_SYNTHETIC_SUBSET"
    assert result.result == {"mean": 120.0, "count": 2, "evidence_refs": ["g1", "g2"]}
    unknown = execute_cql_contract(CqlExecutionRequest(tenant_id="synthetic-t", patient_id="synthetic-p", library_id="wysh.synthetic.rules.v1", expression_id="arbitrary-code", synthetic=True, facts=[]))
    assert unknown.status == "UNCONFIGURED"


def test_unified_assessment_exposes_timeline_and_keeps_risk_unconfigured():
    client = TestClient(create_app(Settings()))
    response = client.post("/v1/reuse-accelerator/unified-assess", json={
        "tenant_id":"synthetic-unified-t", "patient_id":"synthetic-unified-p", "synthetic":True,
        "disease_ids":["diabetes", "hypertension", "chronic-kidney-disease"],
        "measurements":[
            {"measurement_id":"h1", "metric":"hba1c", "value":7.1, "unit":"%", "observed_at":"2026-10-01T00:00:00Z", "source_type":"laboratory"},
            {"measurement_id":"s1", "metric":"bp_systolic", "value":138, "unit":"mmHg", "observed_at":"2026-10-02T00:00:00Z", "source_type":"observation"},
            {"measurement_id":"d1", "metric":"bp_diastolic", "value":86, "unit":"mmHg", "observed_at":"2026-10-02T00:00:00Z", "source_type":"observation"},
            {"measurement_id":"e1", "metric":"egfr", "value":58, "unit":"mL/min/1.73m2", "observed_at":"2026-10-03T00:00:00Z", "source_type":"laboratory"},
        ],
    })
    assert response.status_code == 200
    body = response.json()
    assert len(body["assessments"]) == 3
    assert body["risk_indicators_status"] == "NOT_CONFIGURED"
    assert body["clinical_use_authorized"] is False


def test_standards_fhir_elm_vertical_slice_is_allowlisted_and_evidence_linked():
    root = Path(__file__).parents[2]
    elm = json.loads((root / "../disease-intelligence/cql/wysh-diabetes-glucose-observation-elm.json").resolve().read_text())
    bundle = {
        "resourceType": "Bundle", "type": "collection", "meta": {"tag": [{"code": "synthetic"}]},
        "entry": [{"resource": {"resourceType": "Observation", "id": "glucose-1", "code": {"coding": [{"system": "http://loinc.org", "code": "2339-0"}]}, "valueQuantity": {"value": 65, "unit": "mg/dL"}, "effectiveDateTime": "2026-10-01T00:00:00Z"}}],
    }
    result = execute_fhir_elm_subset(StandardsCqlRequest(tenant_id="synthetic-t", patient_id="synthetic-p", library_id="wysh.diabetes.rules", expression_id="HasGlucoseObservation", elm=elm, bundle=bundle, synthetic=True))
    assert result.status == "EXECUTED_SYNTHETIC_ELM_SUBSET"
    assert result.result == {"present": True, "count": 1}
    assert result.evidence_refs == ["glucose-1"]
    assert result.fhir_version == "4.0.1"
    assert result.clinical_use_authorized is False


def test_standards_fhir_elm_rejects_arbitrary_expression_and_non_synthetic_route():
    root = Path(__file__).parents[2]
    elm = json.loads((root / "../disease-intelligence/cql/wysh-diabetes-glucose-observation-elm.json").resolve().read_text())
    req = StandardsCqlRequest(tenant_id="synthetic-t", patient_id="synthetic-p", library_id="wysh.diabetes.rules", expression_id="arbitrary", elm=elm, bundle={"resourceType": "Bundle", "meta": {"tag": [{"code": "synthetic"}]}, "entry": []}, synthetic=True)
    assert execute_fhir_elm_subset(req).status == "UNCONFIGURED"
    client = TestClient(create_app(Settings()))
    body = req.model_dump(mode="json")
    body["synthetic"] = False
    assert client.post("/v1/reuse-accelerator/fhir-cql/execute", json=body).status_code == 403


def test_pinned_upstream_cql_runtime_executes_only_allowlisted_synthetic_artifact():
    root = Path(__file__).parents[2]
    elm = json.loads((root / "../disease-intelligence/cql/wysh-diabetes-glucose-observation-elm.json").resolve().read_text())
    bundle = {"resourceType": "Bundle", "type": "collection", "meta": {"tag": [{"code": "synthetic"}]}, "entry": [{"resource": {"resourceType": "Patient", "id": "synthetic-runtime-patient"}}, {"resource": {"resourceType": "Observation", "id": "runtime-glucose-1", "code": {"coding": [{"system": "http://loinc.org", "code": "2339-0"}]}, "valueQuantity": {"value": 65, "unit": "mg/dL"}, "effectiveDateTime": "2026-10-01T00:00:00Z"}}]}
    req = StandardsCqlRequest(tenant_id="synthetic-t", patient_id="synthetic-p", library_id="wysh.diabetes.rules", expression_id="HasGlucoseObservation", elm=elm, bundle=bundle, synthetic=True)
    result = execute_pinned_runtime(req)
    assert result.status == "EXECUTED_UPSTREAM_RUNTIME"
    assert result.result["patientResults"]["synthetic-runtime-patient"]["HasGlucoseObservation"] is True
    assert result.clinical_use_authorized is False
    response = TestClient(create_app(Settings())).post("/v1/reuse-accelerator/fhir-cql/upstream-runtime", json=req.model_dump(mode="json"))
    assert response.status_code == 200
    assert response.json()["status"] == "EXECUTED_UPSTREAM_RUNTIME"


def test_upstream_runtime_bounds_missing_patient_invalid_observations_and_request_size():
    root = Path(__file__).parents[2]
    elm = json.loads((root / "../disease-intelligence/cql/wysh-diabetes-glucose-observation-elm.json").resolve().read_text())
    no_patient = {"resourceType": "Bundle", "type": "collection", "meta": {"tag": [{"code": "synthetic"}]}, "entry": [{"resource": {"resourceType": "Observation", "id": "observation-only"}}]}
    req = StandardsCqlRequest(tenant_id="synthetic-t", patient_id="synthetic-p", library_id="wysh.diabetes.rules", expression_id="HasGlucoseObservation", elm=elm, bundle=no_patient, synthetic=True)
    assert execute_pinned_runtime(req).status in {"ABSTAINED", "EXECUTED_UPSTREAM_RUNTIME"}
    oversized = req.model_copy(update={"elm": {"padding": "x" * 80_000}})
    assert execute_pinned_runtime(oversized).status == "ABSTAINED"


def test_versioned_synthetic_terminology_contract_fails_closed():
    valid = validate_code(TerminologyValidationRequest(tenant_id="synthetic-t", system="http://loinc.org", code="2339-0", value_set_url="https://wysh.ai/fhir/ValueSet/synthetic-diabetes-observations", synthetic=True))
    assert valid.status == "VALID"
    unknown = validate_code(TerminologyValidationRequest(tenant_id="synthetic-t", system="http://loinc.org", code="9999-9", synthetic=True))
    assert unknown.status == "NOT_FOUND"
    mismatch = validate_code(TerminologyValidationRequest(tenant_id="synthetic-t", system="http://loinc.org", code="2339-0", display="not glucose", synthetic=True))
    assert mismatch.status == "ABSTAINED"
    client = TestClient(create_app(Settings()))
    body = {"tenant_id": "synthetic-t", "system": "http://loinc.org", "code": "2339-0", "synthetic": False}
    assert client.post("/v1/reuse-accelerator/terminology/validate", json=body).status_code == 403
