"""End-to-end tests for the System One router.

Structured clinical facts in, structured routing decisions out. Synthetic-only,
no PHI, deny-by-default, human review required, clinical use not authorized.
"""

from __future__ import annotations

import pytest

from app.system_one_router import SystemOneRouter, SystemOneRoutingRequest
from app.feature_extractor import ClinicalFact


def _request(**overrides) -> SystemOneRoutingRequest:
    base = dict(
        tenant_id="synthetic-tenant-1",
        patient_id="synthetic-patient-1",
        indication="diabetes",
        facts=[
            ClinicalFact(source_id="obs-1", source_type="observation", metric="hba1c_percent", value=7.2, recorded_at="2026-01-01T00:00:00Z"),
            ClinicalFact(source_id="obs-2", source_type="observation", metric="mean_glucose_mg_dl", value=154.0, recorded_at="2026-01-01T00:00:00Z"),
            ClinicalFact(source_id="obs-3", source_type="observation", metric="age_years", value=55.0, recorded_at="2026-01-01T00:00:00Z"),
        ],
        synthetic=True,
    )
    base.update(overrides)
    return SystemOneRoutingRequest(**base)


def test_end_to_end_returns_structured_decision() -> None:
    router = SystemOneRouter()
    decision = router.route(_request())
    assert decision.system == "system_one"
    assert decision.indication == "diabetes"
    assert decision.decision_id.startswith("system_one-")
    assert decision.human_review_required is True
    assert decision.clinical_use_authorized is False
    assert decision.model_id == "wysh.synthetic.diabetes.review.v1"
    assert decision.model_status == "EXPERIMENTAL"
    assert decision.latency_ms >= 0
    assert len(decision.evidence_used) == 3


def test_non_synthetic_rejected() -> None:
    router = SystemOneRouter()
    with pytest.raises(ValueError):
        router.route(_request(synthetic=False))


def test_non_synthetic_identifiers_rejected() -> None:
    router = SystemOneRouter()
    with pytest.raises(ValueError):
        router.route(_request(tenant_id="real-tenant-1"))


def test_phi_in_context_rejected() -> None:
    router = SystemOneRouter()
    with pytest.raises(ValueError):
        router.route(_request(context={"mrn": "123456", "name": "John Doe"}))


def test_phone_pattern_in_context_rejected() -> None:
    router = SystemOneRouter()
    with pytest.raises(ValueError):
        router.route(_request(context={"contact_phone": "5550123456"}))


def test_missing_required_metrics_abstains() -> None:
    router = SystemOneRouter()
    decision = router.route(_request(indication="diabetes", facts=[]))
    assert decision.abstained is True
    assert decision.selected_action is None
    assert decision.confidence is None
    assert "hba1c_percent" in decision.missing_required_metrics


def test_hypertension_routing() -> None:
    router = SystemOneRouter()
    decision = router.route(
        _request(
            indication="hypertension",
            facts=[
                ClinicalFact(source_id="obs-1", source_type="observation", metric="bp_systolic_mmhg", value=185.0, recorded_at="2026-01-01T00:00:00Z"),
                ClinicalFact(source_id="obs-2", source_type="observation", metric="bp_diastolic_mmhg", value=120.0, recorded_at="2026-01-01T00:00:00Z"),
                ClinicalFact(source_id="obs-3", source_type="observation", metric="age_years", value=60.0, recorded_at="2026-01-01T00:00:00Z"),
            ],
        )
    )
    assert decision.indication == "hypertension"
    assert decision.model_id == "wysh.synthetic.hypertension.review.v1"
    assert decision.human_review_required is True


def test_public_status_deny_by_default() -> None:
    router = SystemOneRouter()
    status = router.public_status()
    assert status["provider_free"] is True
    assert status["clinical_use_authorized"] is False
    assert status["synthetic_only"] is True
    assert status["deny_by_default"] is True
    assert status["human_review_required"] is True
    assert "diabetes" in status["supported_indications"]
