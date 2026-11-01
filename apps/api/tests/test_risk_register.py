"""Tests for the System One ISO 14971 risk register.

Hazard tracking, risk control measures, residual risk, benefit-risk analysis.
Synthetic-only.
"""

from __future__ import annotations

import pytest

from app.system_one.risk_register import (  # noqa
    HazardRecord,
    RiskAcceptability,
    RiskControlMeasure,
    RiskProbability,
    RiskSeverity,
    SystemOneRiskRegister,
)


def test_risk_register_public_status() -> None:
    register = SystemOneRiskRegister()
    status = register.public_status()
    assert status["register_id"] == "wysh.system-one.risk-register.v1"
    assert status["total_hazards"] == 0
    assert status["unmitigated_hazards"] == 0
    assert status["critical_unmitigated"] == 0
    assert status["synthetic_only"] is True
    assert status["clinical_use_authorized"] is False


def test_add_hazard() -> None:
    register = SystemOneRiskRegister()
    hazard = HazardRecord(
        hazard_id="HZ-001",
        hazard_description="Model outputs overconfident wrong triage decision",
        hazardous_situation="Clinician relies on wrong escalation recommendation",
        potential_harm="Delayed care for serious condition",
        harm_severity='CRITICAL',
        initial_probability='POSSIBLE',
        initial_risk_level="HIGH",
        risk_control_measures=["human_handoff_on_low_confidence", "clinician_signoff_required"],
        created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
        control_measure_type='INFORMATION_FOR_SAFETY',
        risk_acceptability='REVIEW_REQUIRED',
    )
    register.add_hazard(hazard)
    status = register.public_status()
    assert status["total_hazards"] == 1
    assert status["unmitigated_hazards"] == 1
    assert status["critical_unmitigated"] == 1


def test_add_duplicate_hazard_raises() -> None:
    register = SystemOneRiskRegister()
    hazard = HazardRecord(
        hazard_id="HZ-001",
        hazard_description="test",
        hazardous_situation="test",
        potential_harm="test",
        harm_severity='MINOR',
        initial_probability='VERY_UNLIKELY',
        initial_risk_level="LOW",
        created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
    )
    register.add_hazard(hazard)
    with pytest.raises(Exception):
        register.add_hazard(hazard)


def test_update_hazard_mitigation() -> None:
    register = SystemOneRiskRegister()
    hazard = HazardRecord(
        hazard_id="HZ-001",
        hazard_description="test",
        hazardous_situation="test",
        potential_harm="test",
        harm_severity='CRITICAL',
        initial_probability='LIKELY',
        initial_risk_level="HIGH",
        risk_acceptability='UNACCEPTABLE',
        created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
    )
    register.add_hazard(hazard)
    updated = register.update_hazard(
        hazard_id="HZ-001",
        residual_probability='VERY_UNLIKELY',
        residual_risk_level="LOW",
        risk_acceptability='ACCEPTABLE',
        benefit_risk_justification="Human handoff reduces residual risk below acceptable threshold",
        reviewer_id="rev-1",
        reviewer_signoff=True,
    )
    assert updated.residual_probability == 'VERY_UNLIKELY'
    assert updated.residual_risk_level == "LOW"
    assert updated.risk_acceptability == 'ACCEPTABLE'
    assert updated.reviewer_id == "rev-1"
    assert updated.reviewer_signoff_timestamp is not None
    status = register.public_status()
    assert status["unmitigated_hazards"] == 0
    assert status["critical_unmitigated"] == 0


def test_update_unknown_hazard_raises() -> None:
    register = SystemOneRiskRegister()
    with pytest.raises(Exception):
        register.update_hazard(hazard_id="HZ-999", risk_acceptability='ACCEPTABLE')


def test_get_hazard() -> None:
    register = SystemOneRiskRegister()
    hazard = HazardRecord(
        hazard_id="HZ-001",
        hazard_description="test",
        hazardous_situation="test",
        potential_harm="test",
        harm_severity='SERIOUS',
        initial_probability='UNLIKELY',
        initial_risk_level="MEDIUM",
        created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
    )
    register.add_hazard(hazard)
    retrieved = register.get_hazard("HZ-001")
    assert retrieved is not None
    assert retrieved.hazard_id == "HZ-001"
    assert retrieved.harm_severity == 'SERIOUS'
    assert register.get_hazard("HZ-999") is None


def test_list_hazards_sorted() -> None:
    register = SystemOneRiskRegister()
    for i in [3, 1, 2]:
        hazard = HazardRecord(
            hazard_id=f"HZ-{i:03d}",
            hazard_description=f"hazard {i}",
            hazardous_situation=f"situation {i}",
            potential_harm=f"harm {i}",
        harm_severity='MINOR',  # noqa
        initial_probability='VERY_UNLIKELY',  # noqa
        initial_risk_level="LOW",  # noqa
        created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",  # noqa
    )  # noqa
        register.add_hazard(hazard)
    hazards = register.list_hazards()
    assert [h.hazard_id for h in hazards] == ["HZ-001", "HZ-002", "HZ-003"]
