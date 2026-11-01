"""Tests for the System One decision heads.

Choice, Score, Noul output primitives. Deterministic, bounded, no text
generation.
"""

from __future__ import annotations

import pytest

from app.system_one.decision_heads import (  # noqa
    ChoiceOutput,
    HeadWeights,
    NoulOutput,
    ScoreOutput,
    SystemOneDecisionHeads,
    default_choice_weights,
    default_noul_weights,
    default_score_weights,
)


def test_default_choice_weights() -> None:
    weights = default_choice_weights("choice-v1", 768, ["review_required", "escalate"])
    assert weights.head_type == "choice"
    assert weights.input_dim == 768
    assert weights.option_labels == ("review_required", "escalate")
    assert len(weights.weights) == 768


def test_default_score_weights() -> None:
    weights = default_score_weights("score-v1", 768)
    assert weights.head_type == "score"
    assert weights.input_dim == 768


def test_default_noul_weights() -> None:
    weights = default_noul_weights("noul-v1", 768)
    assert weights.head_type == "noul"
    assert weights.input_dim == 768


def test_choice_head_selects_option() -> None:
    heads = SystemOneDecisionHeads(embedding_dim=768)
    heads.register_head("choice", default_choice_weights("choice", 768, ["review_required", "escalate", "monitor"]))
    embeddings = tuple(0.1 for _ in range(768))
    result = heads.choice("choice", embeddings, permitted_options=["review_required", "escalate", "monitor"], confidence_threshold=0.5)
    assert isinstance(result, ChoiceOutput)
    assert result.selected_option in {"review_required", "escalate", "monitor"} or result.abstained is True
    assert 0.0 <= result.confidence <= 1.0
    assert len(result.option_probabilities) == 3


def test_choice_head_abstains_below_threshold() -> None:
    heads = SystemOneDecisionHeads(embedding_dim=768)
    heads.register_head("choice", default_choice_weights("choice", 768, ["review_required", "escalate"]))
    embeddings = tuple(0.0 for _ in range(768))
    result = heads.choice("choice", embeddings, permitted_options=["review_required", "escalate"], confidence_threshold=0.99)
    assert result.abstained is True
    assert result.selected_option is None


def test_score_head_output_range() -> None:
    heads = SystemOneDecisionHeads(embedding_dim=768)
    heads.register_head("score", default_score_weights("score", 768))
    embeddings = tuple(0.5 for _ in range(768))
    result = heads.score("score", embeddings, confidence_threshold=0.5)
    assert isinstance(result, ScoreOutput)
    if not result.abstained:
        assert 0.0 <= result.score <= 10.0
    assert 0.0 <= result.confidence <= 1.0


def test_noul_head_output_range() -> None:
    heads = SystemOneDecisionHeads(embedding_dim=768)
    heads.register_head("noul", default_noul_weights("noul", 768))
    embeddings = tuple(0.3 for _ in range(768))
    result = heads.noul("noul", embeddings, confidence_threshold=0.5)
    assert isinstance(result, NoulOutput)
    if not result.abstained:
        assert 0.0 <= result.probability_yes <= 1.0
    assert 0.0 <= result.confidence <= 1.0


def test_unknown_head_raises() -> None:
    heads = SystemOneDecisionHeads(embedding_dim=768)
    embeddings = tuple(0.1 for _ in range(768))
    with pytest.raises(Exception):
        heads.choice("unknown", embeddings, permitted_options=["a", "b"])


def test_wrong_head_type_raises() -> None:
    heads = SystemOneDecisionHeads(embedding_dim=768)
    heads.register_head("score", default_score_weights("score", 768))
    embeddings = tuple(0.1 for _ in range(768))
    with pytest.raises(Exception):
        heads.choice("score", embeddings, permitted_options=["a", "b"])


def test_embedding_dimension_mismatch_raises() -> None:
    heads = SystemOneDecisionHeads(embedding_dim=768)
    heads.register_head("noul", default_noul_weights("noul", 768))
    with pytest.raises(Exception):
        heads.noul("noul", tuple(0.1 for _ in range(100)), confidence_threshold=0.5)


def test_heads_public_status() -> None:
    heads = SystemOneDecisionHeads(embedding_dim=768)
    heads.register_head("choice", default_choice_weights("choice", 768, ["a", "b"]))
    heads.register_head("noul", default_noul_weights("noul", 768))
    status = heads.public_status()
    assert status["embedding_dim"] == 768
    assert "choice" in status["heads"]
    assert "noul" in status["heads"]
    assert status["heads"]["choice"]["head_type"] == "choice"
    assert status["heads"]["noul"]["head_type"] == "noul"
