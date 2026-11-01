"""Synthetic FHIR R4 Observation adapter for WDI monitoring.

Only a small explicit code map is enabled. Unknown codes are ignored rather
than guessed, and the original Bundle is never logged or persisted.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from .disease_intelligence import LongitudinalMeasurement, MonitoringRequest


class FHIRMonitoringRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=200)
    patient_id: str = Field(min_length=1, max_length=200)
    disease_id: str = Field(min_length=1, max_length=100)
    bundle: dict[str, Any]
    synthetic: bool = False

    @field_validator("bundle")
    @classmethod
    def bundle_is_synthetic_collection(cls, value: dict[str, Any]) -> dict[str, Any]:
        if value.get("resourceType") != "Bundle" or value.get("meta", {}).get("tag", [{}])[0].get("code") != "synthetic":
            raise ValueError("only explicitly synthetic FHIR Bundles are accepted")
        return value


CODE_MAP = {
    "4548-4": ("hba1c", "%"),
    "2339-0": ("glucose", "mg/dL"),
    "2160-0": ("creatinine", "mg/dL"),
    "62238-1": ("egfr", "mL/min/1.73m2"),
    "14957-5": ("urine_albumin", "mg/g"),
}


def bundle_to_monitoring(request: FHIRMonitoringRequest) -> MonitoringRequest:
    measurements: list[LongitudinalMeasurement] = []
    for entry in request.bundle.get("entry", []):
        resource = entry.get("resource", {}) if isinstance(entry, dict) else {}
        if resource.get("resourceType") != "Observation":
            continue
        codings = resource.get("code", {}).get("coding", [])
        code = next((item.get("code") for item in codings if item.get("code") in CODE_MAP), None)
        if not code:
            continue
        quantity = resource.get("valueQuantity", {})
        value = quantity.get("value")
        observed_at = resource.get("effectiveDateTime")
        if not isinstance(value, (int, float)) or not isinstance(observed_at, str):
            continue
        metric, default_unit = CODE_MAP[code]
        measurements.append(LongitudinalMeasurement(measurement_id=str(resource.get("id", f"observation-{len(measurements) + 1}")), metric=metric, value=float(value), unit=str(quantity.get("unit", default_unit)), observed_at=observed_at, source_type="laboratory"))
    return MonitoringRequest(tenant_id=request.tenant_id, patient_id=request.patient_id, disease_id=request.disease_id, measurements=measurements, synthetic=True)
