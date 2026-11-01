"""Run synthetic differential checks across native and upstream runtime lanes."""

from __future__ import annotations

import json
from pathlib import Path

from app.standards_cql import StandardsCqlRequest, execute_fhir_elm_subset
from app.terminology import TerminologyValidationRequest, validate_code
from app.upstream_cql_runtime import execute_pinned_runtime


def bundle(with_observation: bool) -> dict:
    entries = [{"resource": {"resourceType": "Patient", "id": "synthetic-r7b-patient"}}]
    if with_observation:
        entries.append({"resource": {"resourceType": "Observation", "id": "synthetic-r7b-glucose", "code": {"coding": [{"system": "http://loinc.org", "code": "2339-0"}]}, "valueQuantity": {"value": 65, "unit": "mg/dL"}, "effectiveDateTime": "2026-10-01T00:00:00Z"}})
    return {"resourceType": "Bundle", "type": "collection", "meta": {"tag": [{"code": "synthetic"}]}, "entry": entries}


def main() -> int:
    root = Path(__file__).parents[3]
    elm = json.loads((root / "disease-intelligence/cql/wysh-diabetes-glucose-observation-elm.json").read_text(encoding="utf-8"))
    positive = StandardsCqlRequest(tenant_id="synthetic-r7b-tenant", patient_id="synthetic-r7b-patient", library_id="wysh.diabetes.rules", expression_id="HasGlucoseObservation", elm=elm, bundle=bundle(True), synthetic=True)
    empty = positive.model_copy(update={"bundle": bundle(False)})
    native_positive = execute_fhir_elm_subset(positive)
    upstream_positive = execute_pinned_runtime(positive)
    native_empty = execute_fhir_elm_subset(empty)
    upstream_empty = execute_pinned_runtime(empty)
    checks = {
        "positive_differential": native_positive.result == {"present": True, "count": 1} and upstream_positive.result["patientResults"]["synthetic-r7b-patient"]["HasGlucoseObservation"] is True,
        "empty_evidence_abstention_aligned": native_empty.status == "ABSTAINED" and upstream_empty.status == "ABSTAINED",
        "terminology_valid": validate_code(TerminologyValidationRequest(tenant_id=positive.tenant_id, system="http://loinc.org", code="2339-0", synthetic=True)).status == "VALID",
        "terminology_unknown_fails_closed": validate_code(TerminologyValidationRequest(tenant_id=positive.tenant_id, system="http://loinc.org", code="unknown", synthetic=True)).status == "NOT_FOUND",
        "synthetic_only": upstream_positive.clinical_use_authorized is False,
    }
    payload = {"suite": "r7b-synthetic-cql-fhir-differential", "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "cql_conformance_claim": "bounded-differential-only", "clinical_validation": "NO-GO", "production": "NO-GO", "synthetic_only": True}
    output = root / "artifacts/r7-test-evidence/r7b-conformance-gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), **payload}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
