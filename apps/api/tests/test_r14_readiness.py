from __future__ import annotations

import json
from pathlib import Path

from app.providers import MEDGEMMA_MAX_OUTPUT_TOKENS


def test_r14_corpus_is_complete_and_synthetic():
    root = Path(__file__).parents[3]
    corpus = json.loads((root / "research/medgemma/r13-challenge-corpus-v1.json").read_text())
    assert corpus["synthetic_only"] is True
    assert len(corpus["cases"]) == 16
    assert corpus["live_subset_size"] == 8
    assert len({case["id"] for case in corpus["cases"]}) == 16


def test_medgemma_output_budget_is_bounded_and_regression_visible():
    assert MEDGEMMA_MAX_OUTPUT_TOKENS == 512
    assert MEDGEMMA_MAX_OUTPUT_TOKENS <= 1024
