"""System One decision heads: Choice, Score, Noul output primitives.

Phase 1 prototype. Three lightweight heads on top of encoder embeddings:

1. Choice: softmax over predefined discrete options + confidence
2. Score: regression to ordinal clinical severity score (0–10)
3. Noul: calibrated probability P(yes) for a binary condition (0–1)

All heads are linear / bounded; no text generation, no structural
hallucinations. Outputs are deterministic given the same embeddings.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Literal

from pydantic import BaseModel, Field


class HeadError(ValueError):
    pass


@dataclass(frozen=True)
class HeadWeights:
    """Linear head weights + bias. Serialized for audit and provenance."""
    head_type: Literal["choice", "score", "noul"]
    weights: tuple[float, ...]
    bias: float
    input_dim: int
    option_labels: tuple[str, ...] = ()
    calibration_temperature: float = 1.0


class ChoiceOutput(BaseModel):
    selected_option: str | None = Field(default=None, max_length=200)
    confidence: float = Field(ge=0.0, le=1.0)
    option_probabilities: dict[str, float] = Field(default_factory=dict)
    abstained: bool = False


class ScoreOutput(BaseModel):
    score: float = Field(ge=0.0, le=10.0)
    confidence: float = Field(ge=0.0, le=1.0)
    abstained: bool = False


class NoulOutput(BaseModel):
    probability_yes: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    abstained: bool = False


class SystemOneDecisionHeads:
    """Choice, Score, Noul heads over encoder embeddings."""

    def __init__(self, embedding_dim: int = 768):
        self._embedding_dim = embedding_dim
        self._heads: dict[str, HeadWeights] = {}

    def register_head(self, head_id: str, weights: HeadWeights) -> None:
        if weights.input_dim != self._embedding_dim:
            raise HeadError(
                f"head input_dim {weights.input_dim} != embedding_dim {self._embedding_dim}"
            )
        if head_id in self._heads:
            raise HeadError(f"head {head_id} is already registered")
        self._heads[head_id] = weights

    def _sigmoid(self, value: float) -> float:
        value = max(-40.0, min(40.0, value))
        return 1.0 / (1.0 + exp(-value))

    def _softmax(self, logits: list[float]) -> list[float]:
        max_logit = max(logits) if logits else 0.0
        exps = [exp(logit - max_logit) for logit in logits]
        total = sum(exps)
        if total <= 0:
            return [1.0 / len(logits)] * len(logits) if logits else []
        return [exp_value / total for exp_value in exps]

    def choice(
        self,
        head_id: str,
        embeddings: tuple[float, ...],
        permitted_options: list[str],
        confidence_threshold: float = 0.5,
    ) -> ChoiceOutput:
        """Choice primitive: pick one discrete option + confidence."""
        if head_id not in self._heads:
            raise HeadError(f"head {head_id} is not registered")
        weights = self._heads[head_id]
        if weights.head_type != "choice":
            raise HeadError(f"head {head_id} is not a choice head")
        if not permitted_options:
            raise HeadError("permitted_options must be non-empty")

        if len(embeddings) != self._embedding_dim:
            raise HeadError(
                f"embeddings dim {len(embeddings)} != {self._embedding_dim}"
            )

        # Compute logits for each option using shared weights + option index bias
        logits: list[float] = []
        for index, option in enumerate(permitted_options):
            logit = weights.bias + sum(
                w * emb for w, emb in zip(weights.weights, embeddings)
            ) + (index * 0.01)  # small option-index bias for determinism
            logits.append(logit)

        probabilities = self._softmax(logits)
        option_probabilities = {
            option: round(prob, 6) for option, prob in zip(permitted_options, probabilities)
        }

        best_index = max(range(len(probabilities)), key=lambda i: probabilities[i])
        best_option = permitted_options[best_index]
        best_confidence = probabilities[best_index]

        abstained = best_confidence < confidence_threshold

        return ChoiceOutput(
            selected_option=None if abstained else best_option,
            confidence=round(best_confidence, 6),
            option_probabilities=option_probabilities,
            abstained=abstained,
        )

    def score(
        self,
        head_id: str,
        embeddings: tuple[float, ...],
        confidence_threshold: float = 0.5,
    ) -> ScoreOutput:
        """Score primitive: ordinal clinical severity score (0–10)."""
        if head_id not in self._heads:
            raise HeadError(f"head {head_id} is not registered")
        weights = self._heads[head_id]
        if weights.head_type != "score":
            raise HeadError(f"head {head_id} is not a score head")

        if len(embeddings) != self._embedding_dim:
            raise HeadError(
                f"embeddings dim {len(embeddings)} != {self._embedding_dim}"
            )

        raw = weights.bias + sum(
            w * emb for w, emb in zip(weights.weights, embeddings)
        )
        # Map raw linear output to 0–10 via sigmoid scaling
        score = round(self._sigmoid(raw) * 10.0, 4)

        # Confidence derived from magnitude of raw output (sigmoid derivative proxy)
        confidence = round(min(abs(raw) / 5.0, 1.0), 6)

        abstained = confidence < confidence_threshold

        return ScoreOutput(
            score=None if abstained else score,
            confidence=confidence,
            abstained=abstained,
        )

    def noul(
        self,
        head_id: str,
        embeddings: tuple[float, ...],
        confidence_threshold: float = 0.5,
    ) -> NoulOutput:
        """Noul primitive: calibrated P(yes) for a binary condition (0–1)."""
        if head_id not in self._heads:
            raise HeadError(f"head {head_id} is not registered")
        weights = self._heads[head_id]
        if weights.head_type != "noul":
            raise HeadError(f"head {head_id} is not a noul head")

        if len(embeddings) != self._embedding_dim:
            raise HeadError(
                f"embeddings dim {len(embeddings)} != {self._embedding_dim}"
            )

        raw = weights.bias + sum(
            w * emb for w, emb in zip(weights.weights, embeddings)
        )
        # Apply calibration temperature before sigmoid
        temperature = max(weights.calibration_temperature, 1e-6)
        probability = round(self._sigmoid(raw / temperature), 6)

        # Confidence: distance from 0.5, scaled
        confidence = round(min(abs(probability - 0.5) * 2.0, 1.0), 6)

        abstained = confidence < confidence_threshold

        return NoulOutput(
            probability_yes=None if abstained else probability,
            confidence=confidence,
            abstained=abstained,
        )

    def public_status(self) -> dict[str, object]:
        return {
            "embedding_dim": self._embedding_dim,
            "heads": {
                head_id: {
                    "head_type": hw.head_type,
                    "input_dim": hw.input_dim,
                    "calibration_temperature": hw.calibration_temperature,
                    "option_count": len(hw.option_labels),
                }
                for head_id, hw in self._heads.items()
            },
        }


def default_choice_weights(
    head_id: str,
    embedding_dim: int,
    option_labels: list[str],
) -> HeadWeights:
    """Deterministic default choice weights (seeded, auditable)."""
    weights = tuple(
        (i * 0.001 - 0.0005) for i in range(embedding_dim)
    )
    return HeadWeights(
        head_type="choice",
        weights=weights,
        bias=0.0,
        input_dim=embedding_dim,
        option_labels=tuple(option_labels),
        calibration_temperature=1.0,
    )


def default_score_weights(head_id: str, embedding_dim: int) -> HeadWeights:
    """Deterministic default score weights (seeded, auditable)."""
    weights = tuple(
        (i * 0.0008 - 0.0004) for i in range(embedding_dim)
    )
    return HeadWeights(
        head_type="score",
        weights=weights,
        bias=0.0,
        input_dim=embedding_dim,
        calibration_temperature=1.0,
    )


def default_noul_weights(head_id: str, embedding_dim: int) -> HeadWeights:
    """Deterministic default noul weights (seeded, auditable)."""
    weights = tuple(
        (i * 0.0012 - 0.0006) for i in range(embedding_dim)
    )
    return HeadWeights(
        head_type="noul",
        weights=weights,
        bias=0.0,
        input_dim=embedding_dim,
        calibration_temperature=1.0,
    )
