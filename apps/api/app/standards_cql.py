"""Small, fail-closed FHIR R4 + JSON ELM execution boundary.

This is an original adapter contract, not a vendored CQL runtime. It accepts
only the one synthetic diabetes observation expression shipped by wysh.AI and
uses the existing FHIR Observation mapping. Full CQL/ELM conformance remains
unconfigured until a pinned upstream runtime is evaluated in an isolated
service.
"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .fhir_adapter import FHIRMonitoringRequest, bundle_to_monitoring


class StandardsCqlRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=200)
    patient_id: str = Field(min_length=1, max_length=200)
    library_id: str = Field(min_length=1, max_length=200)
    expression_id: str = Field(min_length=1, max_length=200)
    elm: dict[str, Any]
    bundle: dict[str, Any]
    synthetic: bool = False

    @field_validator("bundle")
    @classmethod
    def bundle_is_synthetic(cls, value: dict[str, Any]) -> dict[str, Any]:
        if value.get("resourceType") != "Bundle" or value.get("meta", {}).get("tag", [{}])[0].get("code") != "synthetic":
            raise ValueError("only explicitly synthetic FHIR Bundles are accepted")
        return value


class StandardsCqlResponse(BaseModel):
    adapter: Literal["fhir-r4-json-elm-subset"] = "fhir-r4-json-elm-subset"
    status: Literal["EXECUTED_SYNTHETIC_ELM_SUBSET", "ABSTAINED", "UNCONFIGURED"]
    library_id: str
    expression_id: str
    result: dict[str, Any] | None
    evidence_refs: list[str]
    fhir_version: Literal["4.0.1"] = "4.0.1"
    elm_schema: Literal["urn:hl7-org:elm:r1"] = "urn:hl7-org:elm:r1"
    elm_hash: str
    reason: str
    synthetic_only: Literal[True] = True
    clinical_use_authorized: Literal[False] = False


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def execute_fhir_elm_subset(request: StandardsCqlRequest) -> StandardsCqlResponse:
    elm_hash = _digest(request.elm)
    empty = dict(adapter="fhir-r4-json-elm-subset", library_id=request.library_id, expression_id=request.expression_id, result=None, evidence_refs=[], elm_hash=elm_hash)
    if request.library_id != "wysh.diabetes.rules" or request.expression_id != "HasGlucoseObservation":
        return StandardsCqlResponse(**empty, status="UNCONFIGURED", reason="Only the pinned synthetic diabetes expression is enabled; arbitrary CQL/ELM is not executed.")
    library = request.elm.get("library")
    if not isinstance(library, dict) or library.get("identifier", {}).get("id") != request.library_id or library.get("schemaIdentifier", {}).get("id") != "urn:hl7-org:elm":
        return StandardsCqlResponse(**empty, status="ABSTAINED", reason="ELM library identity or schema binding is invalid.")
    statements = library.get("statements", {}).get("def", [])
    statement = next((item for item in statements if isinstance(item, dict) and item.get("name") == request.expression_id), None)
    expression = statement.get("expression") if isinstance(statement, dict) else None
    if not isinstance(expression, dict) or expression.get("type") != "Exists":
        return StandardsCqlResponse(**empty, status="ABSTAINED", reason="The expression is not the reviewed Exists-over-FHIR-Observation shape.")
    operand = expression.get("operand")
    if not isinstance(operand, dict) or operand.get("type") != "Retrieve" or operand.get("dataType") != "FHIR.Observation":
        return StandardsCqlResponse(**empty, status="ABSTAINED", reason="The expression does not retrieve FHIR R4 Observation resources.")
    try:
        monitoring = bundle_to_monitoring(FHIRMonitoringRequest(tenant_id=request.tenant_id, patient_id=request.patient_id, disease_id="diabetes", bundle=request.bundle, synthetic=True))
    except ValueError:
        return StandardsCqlResponse(**empty, status="ABSTAINED", reason="FHIR observations could not be mapped into the pinned synthetic data contract.")
    refs = [item.measurement_id for item in monitoring.measurements if item.metric == "glucose"]
    return StandardsCqlResponse(**{**empty, "status": "EXECUTED_SYNTHETIC_ELM_SUBSET", "result": {"present": bool(refs), "count": len(refs)}, "evidence_refs": refs, "reason": "Pinned JSON ELM Exists expression executed against synthetic FHIR R4 Observations; no clinical decision was produced."})
