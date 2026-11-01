"""Tests for the System One RLCD calibration engine.

Temperature scaling, confidence threshold, abstention, reward function,
Expected Calibration Error (ECE). Synthetic-only.
"""

from __future__ import annotations

import pytest

from app.system_one.rlcd import RLCDConfig, RLCDError, SystemOneRLCD


def test_default_rlcd_config() -> None:
    config = RLCDConfig()
    assert config.temperature == 1.0
    assert config.abstention_threshold == 0.85
    assert config.overconfidence_penalty == 0.5
    assert config.calibration_bins == 10
    assert config.synthetic_only is True
    assert config.clinical_use_authorized is False


def test_rlcd_public_status() -> None:
    rlcd = SystemOneRLCD()
    status = rlcd.public_status()
    assert status["temperature"] == 1.0
    assert status["abstention_threshold"] == 0.85
    assert status["total_records"] == 0


def test_noul_calibration_basic() -> None:
    rlcd = SystemOneRLCD()
    record = rlcd.calibrate_noul(
        record_id="cal-1",
        model_id="wysh.system-one.noul.v1",
        raw_logit=2.0,
        actual_outcome=1,
    )
    assert record.record_id == "cal-1"
    assert record.model_id == "wysh.system-one.noul.v1"
    assert record.head_type == "noul"
    assert 0.0 <= record.predicted_probability <= 1.0
    assert 0.0 <= record.confidence <= 1.0
    assert record.temperature == 1.0
    assert record.abstained in {True, False}
    assert record.human_handoff == record.abstained


def test_noul_calibration_duplicate_record_id_raises() -> None:
    rlcd = SystemOneRLCD()
    rlcd.calibrate_noul(record_id="cal-1", model_id="m1", raw_logit=0.0, actual_outcome=1)
    with pytest.raises(RLCDError):
        rlcd.calibrate_noul(record_id="cal-1", model_id="m1", raw_logit=0.0, actual_outcome=0)


def test_noul_high_confidence_not_abstained() -> None:
    rlcd = SystemOneRLCD()
    # High logit → high probability → high confidence → not abstained
    record = rlcd.calibrate_noul(
        record_id="cal-high",
        model_id="m1",
        raw_logit=10.0,
        actual_outcome=1,
    )
    assert record.predicted_probability > 0.9
    assert record.confidence > 0.85
    assert record.abstained is False


def test_noul_low_confidence_abstained() -> None:
    rlcd = SystemOneRLCD()
    # Logit near 0 → probability near 0.5 → low confidence → abstained
    record = rlcd.calibrate_noul(
        record_id="cal-low",
        model_id="m1",
        raw_logit=0.0,
        actual_outcome=1,
    )
    assert record.confidence < 0.85
    assert record.abstained is True
    assert record.human_handoff is True


def test_choice_calibration() -> None:
    rlcd = SystemOneRLCD()
    record = rlcd.calibrate_choice(
        record_id="cal-choice-1",
        model_id="wysh.system-one.choice.v1",
        option_probabilities={"review_required": 0.7, "escalate": 0.2, "monitor": 0.1},
        selected_option="review_required",
        actual_outcome="review_required",
    )
    assert record.head_type == "choice"
    assert record.predicted_probability == 0.7
    assert record.confidence == 0.7
    assert record.actual_outcome == 1  # selected matched actual


def test_choice_calibration_wrong_prediction() -> None:
    rlcd = SystemOneRLCD()
    record = rlcd.calibrate_choice(
        record_id="cal-choice-2",
        model_id="m1",
        option_probabilities={"review_required": 0.7, "escalate": 0.2, "monitor": 0.1},
        selected_option="review_required",
        actual_outcome="escalate",
    )
    assert record.actual_outcome == 0  # selected did not match actual


def test_reward_correct_well_calibrated() -> None:
    rlcd = SystemOneRLCD()
    rlcd.calibrate_noul(record_id="r-1", model_id="m1", raw_logit=3.0, actual_outcome=1)
    result = rlcd.reward(record_id="r-1", reviewer_correct=True, reviewer_confidence=0.9)
    assert result["record_id"] == "r-1"
    assert result["reward"] > 0
    assert result["reason"] == "correct_well_calibrated"
    assert result["clinical_use_authorized"] is False


def test_reward_incorrect_overconfidence_penalty() -> None:
    rlcd = SystemOneRLCD()
    rlcd.calibrate_noul(record_id="r-2", model_id="m1", raw_logit=10.0, actual_outcome=0)
    result = rlcd.reward(record_id="r-2", reviewer_correct=False, reviewer_confidence=0.9)
    assert result["reward"] < 0
    assert "overconfidence_penalty" in result["reason"]


def test_reward_abstained_safe_default() -> None:
    rlcd = SystemOneRLCD()
    rlcd.calibrate_noul(record_id="r-3", model_id="m1", raw_logit=0.0, actual_outcome=1)
    result = rlcd.reward(record_id="r-3", reviewer_correct=False, reviewer_confidence=0.9)
    assert result["reward"] == 0.0
    assert result["reason"] == "abstained_safe_default"


def test_reward_unknown_record_raises() -> None:
    rlcd = SystemOneRLCD()
    with pytest.raises(RLCDError):
        rlcd.reward(record_id="nonexistent", reviewer_correct=True, reviewer_confidence=0.9)


def test_expected_calibration_error_insufficient_sample() -> None:
    rlcd = SystemOneRLCD()
    result = rlcd.expected_calibration_error("noul")
    assert result["status"] == "INSUFFICIENT_SAMPLE"
    assert result["ece"] is None


def test_expected_calibration_error_with_labels() -> None:
    rlcd = SystemOneRLCD(RLCDConfig(abstention_threshold=0.0))
    # Add labeled records across confidence bins
    for i in range(15):
        logit = (i - 7) * 0.5  # spread of logits
        actual = 1 if logit > 0 else 0
        rlcd.calibrate_noul(
            record_id=f"ece-{i}",
            model_id="m1",
            raw_logit=logit,
            actual_outcome=actual,
        )
    result = rlcd.expected_calibration_error("noul")
    assert result["status"] in {"CALIBRATED", "NEEDS_RECALIBRATION", "POOR_CALIBRATION"}
    assert result["ece"] is not None
    assert result["n_labeled"] == 15
    assert len(result["bins"]) > 0


def test_abstention_rate() -> None:
    rlcd = SystemOneRLCD()
    result = rlcd.abstention_rate("noul")
    assert result["abstention_rate"] is None
    assert result["n_total"] == 0

    rlcd.calibrate_noul(record_id="a-1", model_id="m1", raw_logit=0.0, actual_outcome=1)
    rlcd.calibrate_noul(record_id="a-2", model_id="m1", raw_logit=5.0, actual_outcome=1)
    result = rlcd.abstention_rate("noul")
    assert result["n_total"] == 2
    assert result["abstention_rate"] is not None
    assert 0.0 <= result["abstention_rate"] <= 1.0
