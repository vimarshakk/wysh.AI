"""Tests for the System One encoder module.

Deterministic feature-based encoding, multi-lingual support, and fail-closed
behavior. No torch/transformers required for these tests.
"""

from __future__ import annotations

import pytest

from app.system_one.encoder import (
    EncoderConfig,
    SUPPORTED_LANGUAGES,
    SystemOneEncoder,
    default_encoder_config,
)


def test_default_encoder_config() -> None:
    config = default_encoder_config("wysh.system-one.encoder.v1", "en")
    assert config.model_id == "wysh.system-one.encoder.v1"
    assert config.language == "en"
    assert config.parameter_target == 421_000_000
    assert config.embedding_dim == 768
    assert config.synthetic_only is True
    assert config.clinical_use_authorized is False
    assert config.is_encoder_only is True


def test_encoder_supports_all_languages() -> None:
    assert "en" in SUPPORTED_LANGUAGES
    assert "hi" in SUPPORTED_LANGUAGES
    assert "te" in SUPPORTED_LANGUAGES
    assert "ta" in SUPPORTED_LANGUAGES
    assert "bn" in SUPPORTED_LANGUAGES
    assert "mr" in SUPPORTED_LANGUAGES
    assert "es" in SUPPORTED_LANGUAGES
    assert "zh" in SUPPORTED_LANGUAGES
    assert "ar" in SUPPORTED_LANGUAGES
    assert "fr" in SUPPORTED_LANGUAGES
    assert len(SUPPORTED_LANGUAGES) == 10


def test_encoder_deterministic_output() -> None:
    config = default_encoder_config("test-encoder-v1", "en")
    encoder = SystemOneEncoder(config)
    facts_json = json_facts()
    output1 = encoder.encode("en", facts_json)
    output2 = encoder.encode("en", facts_json)
    assert output1.embeddings == output2.embeddings
    assert output1.input_hash == output2.input_hash
    assert output1.deterministic_fallback is True
    assert output1.model_id == "test-encoder-v1"
    assert output1.language == "en"
    assert output1.latency_ms >= 0


def test_encoder_multilingual_same_input_different_language() -> None:
    config = default_encoder_config("test-encoder-v1", "en")
    encoder = SystemOneEncoder(config)
    facts_json = json_facts()
    output_en = encoder.encode("en", facts_json)
    output_hi = encoder.encode("hi", facts_json)
    # Different language → different embeddings (language one-hot differs)
    assert output_en.embeddings != output_hi.embeddings
    assert output_en.language == "en"
    assert output_hi.language == "hi"


def test_encoder_unsupported_language_raises() -> None:
    config = default_encoder_config("test-encoder-v1", "en")
    encoder = SystemOneEncoder(config)
    with pytest.raises(Exception):
        encoder.encode("xx", json_facts())


def test_encoder_embedding_dimension() -> None:
    config = default_encoder_config("test-encoder-v1", "en")
    encoder = SystemOneEncoder(config)
    output = encoder.encode("en", json_facts())
    assert len(output.embeddings) == config.embedding_dim


def test_encoder_public_status() -> None:
    config = default_encoder_config("test-encoder-v1", "hi")
    encoder = SystemOneEncoder(config)
    status = encoder.public_status()
    assert status["model_id"] == "test-encoder-v1"
    assert status["language"] == "hi"
    assert status["parameter_target"] == 421_000_000
    assert status["deterministic_fallback"] is True
    assert status["synthetic_only"] is True
    assert status["clinical_use_authorized"] is False
    assert "en" in status["supported_languages"]


def test_encoder_custom_embedding_dim() -> None:
    config = EncoderConfig(
        model_id="custom-dim-v1",
        backbone="modernbert-base",
        parameter_target=421_000_000,
        language="en",
        embedding_dim=256,
        synthetic_only=True,
        clinical_use_authorized=False,
    )
    encoder = SystemOneEncoder(config)
    output = encoder.encode("en", json_facts())
    assert len(output.embeddings) == 256


def json_facts() -> str:
    import json as _json

    return _json.dumps(
        [
            {"source_id": "obs-1", "source_type": "observation", "metric": "hba1c_percent", "value": 7.2, "recorded_at": "2026-01-01T00:00:00Z"},
            {"source_id": "obs-2", "source_type": "observation", "metric": "mean_glucose_mg_dl", "value": 154.0, "recorded_at": "2026-01-01T00:00:00Z"},
            {"source_id": "cond-1", "source_type": "condition", "code": "diabetes", "recorded_at": "2026-01-01T00:00:00Z"},
        ]
    )
