"""Run the synthetic FHIR R4 + JSON ELM vertical-slice gate."""

from __future__ import annotations

import json
from pathlib import Path

from app.standards_cql import StandardsCqlRequest, execute_fhir_elm_subset


def main() -> int:
    root = Path(__file__).parents[3]
    elm = json.loads((root / "disease-intelligence/cql/wysh-diabetes-glucose-observation-elm.json").read_text(encoding="utf-8"))
    bundle = {"resourceType": "Bundle", "type": "collection", "meta": {"tag": [{"code": "synthetic"}]}, "entry": [{"resource": {"resourceType": "Observation", "id": "synthetic-glucose-1", "code": {"coding": [{"system": "http://loinc.org", "code": "2339-0"}]}, "valueQuantity": {"value": 65, "unit": "mg/dL"}, "effectiveDateTime": "2026-10-01T00:00:00Z"}}]}
    request = StandardsCqlRequest(tenant_id="synthetic-r6c-tenant", patient_id="synthetic-r6c-patient", library_id="wysh.diabetes.rules", expression_id="HasGlucoseObservation", elm=elm, bundle=bundle, synthetic=True)
    executed = execute_fhir_elm_subset(request)
    unknown = execute_fhir_elm_subset(request.model_copy(update={"expression_id": "arbitrary"}))
    checks = {"fhir_r4_observation_mapped": executed.status == "EXECUTED_SYNTHETIC_ELM_SUBSET" and executed.evidence_refs == ["synthetic-glucose-1"], "elm_identity_bound": executed.elm_schema == "urn:hl7-org:elm:r1" and len(executed.elm_hash) == 64, "arbitrary_expression_rejected": unknown.status == "UNCONFIGURED", "clinical_use_disabled": executed.clinical_use_authorized is False}
    payload = {"suite": "synthetic-r6c-fhir-r4-json-elm-gate", "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "runtime_claim": "allowlisted-json-elm-subset-only", "clinical_validation": "NO-GO", "production": "NO-GO", "synthetic_only": True}
    output = root / "artifacts/r6-test-evidence/r6c-standards-gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), **payload}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
