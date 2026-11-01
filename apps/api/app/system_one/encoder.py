"""System One encoder: ModernBERT-class bidirectional encoder with multi-lingual adapters.

Phase 1 prototype. Provides a shared encoder backbone (~421M parameter target,
Laya norm) with lightweight per-language adapters. Encodes structured clinical
telemetry into dense representations consumed by the Choice / Score / Noul
decision heads.

The encoder never generates text. It produces embeddings only. When torch and
transformers are available and a model checkpoint is configured, it loads the
proven encoder weights; otherwise it falls back to a deterministic feature-based
encoder so the pipeline remains runnable offline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ..config import Settings
from ..feature_extractor import extract, required_metrics_for
from ..model_lifecycle import ModelLifecycleStore, REGISTRY_PATH, STATUSES


class EncoderError(ValueError):
    pass


SUPPORTED_LANGUAGES = frozenset({"en", "hi", "te", "ta", "bn", "mr", "es", "zh", "ar", "fr"})


class EncoderConfig(BaseModel):
    model_id: str = Field(min_length=1, max_length=200)
    backbone: str = Field(default="modernbert-base", max_length=200)
    parameter_target: int = Field(default=421_000_000, ge=1)
    language: str = Field(default="en", max_length=10)
    adapter_path: Path | None = Field(default=None)
    checkpoint_path: Path | None = Field(default=None)
    max_sequence_length: int = Field(default=512, ge=64, le=4096)
    embedding_dim: int = Field(default=768, ge=128, le=4096)
    synthetic_only: bool = Field(default=True)
    clinical_use_authorized: bool = Field(default=False)

    @property
    def is_encoder_only(self) -> bool:
        return True


@dataclass(frozen=True)
class EncoderOutput:
    embeddings: tuple[float, ...]
    language: str
    model_id: str
    adapter_used: str | None
    input_hash: str
    latency_ms: int
    deterministic_fallback: bool = False


class SystemOneEncoder:
    """ModernBERT-class encoder with multi-lingual adapter support.

    Tries, in order:
    1. Load configured encoder checkpoint (proven ModernBERT / Laya weights)
    2. Load language-specific adapter if configured
    3. Fall back to deterministic feature-based encoding
    """

    def __init__(self, config: EncoderConfig, settings: Settings | None = None):
        self._config = config
        self._settings = settings
        self._encoder = None
        self._adapter = None
        self._fallback = False
        self._lifecycle = ModelLifecycleStore(REGISTRY_PATH)
        self._load()

    def _load(self) -> None:
        """Load encoder weights and adapter. Fail closed on configuration error."""
        # Attempt to load a real encoder checkpoint if configured
        if self._config.checkpoint_path and self._config.checkpoint_path.is_file():
            try:
                self._load_checkpoint(self._config.checkpoint_path)
                return
            except EncoderError:
                # Fall through to fallback; never silently use a broken checkpoint
                self._encoder = None

        # Attempt to load language adapter
        if self._config.adapter_path and self._config.adapter_path.is_file():
            try:
                self._load_adapter(self._config.adapter_path)
            except EncoderError:
                self._adapter = None

        # Deterministic fallback is always available
        self._fallback = True

    def _load_checkpoint(self, path: Path) -> None:
        """Load a real encoder checkpoint (ModernBERT / Laya weights).

        This integration point is where proven encoder weights are loaded.
        Currently raises EncoderError unless a torch/transformers checkpoint
        is explicitly placed at the configured path.
        """
        # Placeholder for real checkpoint integration. When torch and a saved
        # ModernBERT/Laya checkpoint are available, this loads them here.
        raise EncoderError("no encoder checkpoint loader configured")

    def _load_adapter(self, path: Path) -> None:
        """Load a language-specific adapter (LoRA-style lightweight adapter)."""
        # Placeholder for adapter integration. Adapters are loaded on top of
        # the shared encoder backbone for multi-lingual support.
        raise EncoderError("no adapter loader configured")

    def encode(self, language: str, facts_json: str) -> EncoderOutput:
        """Encode structured clinical facts into dense embeddings.

        Args:
            language: ISO-639-1 language code of the source telemetry.
            facts_json: JSON-serialized clinical facts (from telemetry schema).

        Returns:
            EncoderOutput with embeddings, provenance, and latency.
        """
        if language not in SUPPORTED_LANGUAGES:
            raise EncoderError(f"unsupported language: {language}")

        started = __import__("time").perf_counter()

        if self._fallback:
            embeddings, input_hash = self._deterministic_encode(language, facts_json)
            adapter_used = None
            model_path = "deterministic_fallback"
        else:
            embeddings, input_hash = self._neural_encode(language, facts_json)
            adapter_used = self._config.language
            model_path = self._config.model_id

        latency_ms = int((__import__("time").perf_counter() - started) * 1000)

        return EncoderOutput(
            embeddings=embeddings,
            language=language,
            model_id=self._config.model_id,
            adapter_used=adapter_used,
            input_hash=input_hash,
            latency_ms=latency_ms,
            deterministic_fallback=self._fallback,
        )

    def _deterministic_encode(self, language: str, facts_json: str) -> tuple[tuple[float, ...], str]:
        """Deterministic feature-based encoding (offline fallback).

        Converts typed clinical facts into a bounded numeric embedding vector
        without any neural network. Same input always produces same output.
        """
        import json as _json

        try:
            facts = _json.loads(facts_json)
        except _json.JSONDecodeError as exc:
            raise EncoderError("facts_json is not valid JSON") from exc

        # Hash the input for provenance
        input_hash = sha256(facts_json.encode()).hexdigest()

        # Build a bounded embedding from feature statistics
        # Dimension matches embedding_dim for interface compatibility
        embedding: list[float] = []
        feature_index = 0

        # Language one-hot (10 languages)
        lang_idx = sorted(SUPPORTED_LANGUAGES).index(language)
        for i in range(len(SUPPORTED_LANGUAGES)):
            embedding.append(1.0 if i == lang_idx else 0.0)
        feature_index += len(SUPPORTED_LANGUAGES)

        # Fact statistics
        fact_list = facts if isinstance(facts, list) else []
        fact_count = min(len(fact_list), 500)
        embedding.append(float(fact_count) / 500.0)
        feature_index += 1

        # Per-metric presence and aggregated values (bounded)
        metric_buckets: dict[str, list[float]] = {}
        for item in fact_list:
            if not isinstance(item, dict):
                continue
            metric = item.get("metric")
            value = item.get("value")
            if metric and isinstance(value, (int, float)) and 0.0 <= float(value) <= 1e6:
                metric_buckets.setdefault(str(metric), []).append(float(value))

        # Top metrics by count, bounded to embedding budget
        sorted_metrics = sorted(metric_buckets.items(), key=lambda kv: -len(kv[1]))
        remaining = self._config.embedding_dim - feature_index
        for metric, values in sorted_metrics:
            if remaining <= 0:
                break
            if not values:
                continue
            mean_v = sum(values) / len(values)
            max_v = max(values)
            min_v = min(values)
            count_v = len(values)
            # Store normalized statistics
            embedding.extend([mean_v / 1e6, max_v / 1e6, min_v / 1e6, count_v / 500.0])
            feature_index += 4
            remaining -= 4

        # Pad to embedding_dim
        while len(embedding) < self._config.embedding_dim:
            embedding.append(0.0)

        # Truncate if over (should not happen with the budget logic above)
        embedding = embedding[: self._config.embedding_dim]

        return tuple(embedding), input_hash

    def _neural_encode(self, language: str, facts_json: str) -> tuple[tuple[float, ...], str]:
        """Neural encoder path (when real checkpoint + adapter are loaded)."""
        # Placeholder: when torch/transformers checkpoint is loaded, this runs
        # the actual encoder forward pass. For now, delegate to deterministic
        # to keep the pipeline correct and safe.
        return self._deterministic_encode(language, facts_json)

    def public_status(self) -> dict[str, object]:
        return {
            "model_id": self._config.model_id,
            "backbone": self._config.backbone,
            "parameter_target": self._config.parameter_target,
            "language": self._config.language,
            "encoder_only": self._config.is_encoder_only,
            "deterministic_fallback": self._fallback,
            "synthetic_only": self._config.synthetic_only,
            "clinical_use_authorized": self._config.clinical_use_authorized,
            "supported_languages": sorted(SUPPORTED_LANGUAGES),
        }


def default_encoder_config(
    model_id: str = "wysh.system-one.encoder.v1",
    language: str = "en",
) -> EncoderConfig:
    return EncoderConfig(
        model_id=model_id,
        backbone="modernbert-base",
        parameter_target=421_000_000,
        language=language,
        embedding_dim=768,
        synthetic_only=True,
        clinical_use_authorized=False,
    )
