"""Synthetic FHIR/ABDM-compatible boundary contracts for R11D."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SyntheticAbdmConsentContext(BaseModel):
    consent_id: str = Field(min_length=1, max_length=200)
    purpose: Literal["synthetic-evaluation"]
    hi_types: list[Literal["DiagnosticReport", "Observation", "ImagingStudy", "CarePlan"]] = Field(min_length=1, max_length=10)
    patient_reference: str = Field(min_length=1, max_length=200)
    requester_reference: str = Field(min_length=1, max_length=200)
    status: Literal["GRANTED", "REVOKED"] = "GRANTED"
    synthetic: Literal[True] = True

    @field_validator("patient_reference")
    @classmethod
    def synthetic_patient(cls, value: str) -> str:
        if not value.startswith("Patient/synthetic-"):
            raise ValueError("only synthetic patient references are accepted")
        return value


class SyntheticAbdmExchange(BaseModel):
    protocol: Literal["ABDM-HIE-CM-COMPATIBLE"] = "ABDM-HIE-CM-COMPATIBLE"
    consent: SyntheticAbdmConsentContext
    fhir_bundle: dict
    provenance_hash: str = Field(min_length=64, max_length=64)
    synthetic: Literal[True] = True

    @field_validator("fhir_bundle")
    @classmethod
    def synthetic_bundle(cls, value: dict) -> dict:
        if value.get("resourceType") != "Bundle" or value.get("meta", {}).get("tag", [{}])[0].get("code") != "synthetic":
            raise ValueError("FHIR bundle must carry the synthetic marker")
        return value


def validate_exchange_scope(exchange: SyntheticAbdmExchange) -> dict[str, str]:
    patient_id = exchange.consent.patient_reference.split("/", 1)[1]
    bundle_patient_ids = [entry.get("resource", {}).get("id") for entry in exchange.fhir_bundle.get("entry", []) if entry.get("resource", {}).get("resourceType") == "Patient"]
    if patient_id not in bundle_patient_ids:
        return {"status": "ABSTAINED", "reason": "consent patient is not the FHIR Bundle patient"}
    if exchange.consent.status != "GRANTED":
        return {"status": "ABSTAINED", "reason": "consent is not granted"}
    return {"status": "PASS", "reason": "synthetic consent and FHIR patient scope match"}
