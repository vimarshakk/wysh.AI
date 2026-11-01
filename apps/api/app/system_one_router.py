"""System One decision router: structured clinical facts in, structured routing decisions out.

The hot path is deterministic and provider-free: feature extraction, model
selection, and threshold/logistic inference. MedGemma and other System Two
providers remain gated behind the existing decision service and are never part
of this fast path. All output is synthetic-only; clinical use is not authorized.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import re
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from .config import Settings
from .decision_model import DecisionAction, SystemOneDecision, SystemOneDecisionModel
from .feature_extractor import ClinicalFact, extract, required_metrics_for
from .model_lifecycle import ModelLifecycleStore
from .routing_engine import RoutingEngine

INDICATION_MODEL_MAP = {
    "diabetes": "wysh.synthetic.diabetes.review.v1",
    "hypertension": "wysh.synthetic.hypertension.review.v1",
    "chronic_kidney_disease": "wysh.synthetic.ckd.review.v1",
}


class SystemOneRoutingRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=200)
    patient_id: str = Field(min_length=1, max_length=200)
    indication: Literal["diabetes", "hypertension", "chronic_kidney_disease", "general"]
    facts: list[ClinicalFact] = Field(default_factory=list, max_length=500)
    context: dict[str, str | int | float | bool | None] = Field(default_factory=dict, max_length=20)
    synthetic: bool = False

    @field_validator("tenant_id", "patient_id")
    @classmethod
    def synthetic_identifiers_only(cls, value: str) -> str:
        if not value.startswith("synthetic-"):
            raise ValueError("tenant and patient identifiers must be synthetic")
        return value

    @field_validator("context")
    @classmethod
    def no_phi_in_context(cls, value: dict[str, str | int | float | bool | None]) -> dict[str, str | int | float | bool | None]:
        forbidden = {"name", "full_name", "email", "phone", "mobile", "address", "dob", "date_of_birth", "aadhaar", "mrn", "medical_record_number", "ssn", "free_text", "document"}
        if forbidden.intersection(key.lower() for key in value):
            raise ValueError("context contains a prohibited identifier or raw-text field")
        serialized = json.dumps(value, sort_keys=True)
        if re.search(r"(?:\b\d{10}\b|\b\d{12}\b|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})", serialized):
            raise ValueError("context contains a prohibited identifier pattern")
        return value

    @field_validator("synthetic")
    @classmethod
    def must_be_synthetic(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("system one routing accepts synthetic requests only")
        return value


class SystemOneRouter:
    """Main System One entry point. Fast, deterministic, provider-free routing."""

    def __init__(self, settings: Settings | None = None):
        self._settings = settings
        self._decision_model = SystemOneDecisionModel()
        self._routing_engine = RoutingEngine(self._decision_model)
        self._lifecycle = ModelLifecycleStore()

    def route(self, request: SystemOneRoutingRequest) -> SystemOneDecision:
        started = datetime.now(timezone.utc)
        feature_vector = extract(request.facts)

        missing_for_indication = [
            metric for metric in required_metrics_for(request.indication)
            if f"{metric}_count" in feature_vector.feature_names
            and feature_vector.values[feature_vector.feature_names.index(f"{metric}_count")] <= 0
        ]

        routing_result = self._routing_engine.route(request.indication, feature_vector)

        if missing_for_indication and not routing_result.abstained:
            routing_result = replace(
                routing_result,
                abstained=True,
                abstention_reason="required metrics missing for indication",
                selected_action=None,
                confidence=None,
            )

        model_id = routing_result.selected_model or ""
        model_status = "UNREGISTERED"
        if model_id:
            try:
                entry = self._lifecycle.get(model_id)
                model_status = entry.get("status", "UNREGISTERED")
            except Exception:
                model_status = "UNREGISTERED"

        clinical_use_authorized = model_status == "CLINICALLY_APPROVED" and not routing_result.abstained

        latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)

        return SystemOneDecision(
            decision_id=f"system_one-{uuid4()}",
            indication=request.indication,
            selected_action=routing_result.selected_action,
            route=routing_result.model_path,
            confidence=routing_result.confidence,
            abstained=routing_result.abstained,
            abstention_reason=routing_result.abstention_reason,
            model_id=model_id,
            model_status=model_status,
            feature_hash=feature_vector.input_hash,
            evidence_used=[fact.source_id for fact in request.facts],
            missing_required_metrics=missing_for_indication,
            human_review_required=True,
            clinical_use_authorized=clinical_use_authorized,
            latency_ms=latency_ms,
        )

    def public_status(self) -> dict[str, object]:
        return {
            "system": "system_one",
            "provider_free": True,
            "clinical_use_authorized": False,
            "synthetic_only": True,
            "supported_indications": list(INDICATION_MODEL_MAP.keys()),
            "inference_enabled": self._settings.inference_enabled if self._settings else False,
            "deny_by_default": True,
            "human_review_required": True,
        }
