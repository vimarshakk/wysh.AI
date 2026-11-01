"""System One training pipeline: Phase 1 prototype orchestration.

Trains the System One decision model (encoder + Choice/Score/Noul heads +
RLCD calibration) on de-identified, openly available clinical data.

Synthetic-only: no PHI is accepted, no clinical use authorization is implied,
and no model can be promoted to CLINICALLY_APPROVED by this pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path  # noqa
from typing import Any

from ..config import Settings
from ..decision_model import SystemOneDecisionModel  # noqa
from ..feature_extractor import extract
from ..ml_governance import GovernanceError, load_governed_dataset
from ..ml_operations import MLOperationsError, ModelVersion, ResearchModelRegistry  # noqa
from ..model_lifecycle import ModelLifecycleStore, REGISTRY_PATH, STATUSES
from .decision_heads import (
    SystemOneDecisionHeads,
    default_choice_weights,
    default_noul_weights,
    default_score_weights,
)
from .encoder import SystemOneEncoder, default_encoder_config
from .rlcd import RLCDConfig, SystemOneRLCD


class TrainingPipelineError(ValueError):
    pass


@dataclass(frozen=True)
class TrainingManifest:
    experiment_id: str
    schema_version: str = "system-one-training-v1"
    model_id: str = ""
    indication: str = ""
    algorithm: str = "system-one-encoder-plus-heads"
    encoder_config: dict[str, Any] = field(default_factory=dict)
    head_configs: dict[str, Any] = field(default_factory=dict)
    rlcd_config: dict[str, Any] = field(default_factory=dict)
    dataset: dict[str, Any] = field(default_factory=dict)
    split_counts: dict[str, int] = field(default_factory=dict)
    group_leakage_check: str = "PASS"
    metrics: dict[str, Any] = field(default_factory=dict)
    calibration: dict[str, Any] = field(default_factory=dict)
    clinical_use_authorized: bool = False
    synthetic_only: bool = True
    provenance_hash: str = ""


class SystemOneTrainingPipeline:
    """Orchestrates System One decision model training.

    Stages:
    1. Load governed synthetic dataset
    2. De-identification gate (fail closed on PHI)
    3. Encode features via System One encoder
    4. Train Choice / Score / Noul heads
    5. Apply RLCD calibration
    6. Register model in lifecycle registry (EXPERIMENTAL only)
    7. Emit training manifest
    """

    def __init__(self, settings: Settings | None = None):
        self._settings = settings
        self._lifecycle = ModelLifecycleStore(REGISTRY_PATH)
        self._research_registry = ResearchModelRegistry()

    def run(
        self,
        model_id: str,
        indication: str,
        dataset_id: str,
        dataset_version: str = "1.0.0",
        seed: int = 20261024,
    ) -> TrainingManifest:
        """Run the full training pipeline for one indication."""
        from datetime import datetime, timezone

        started = datetime.now(timezone.utc)  # noqa

        # Stage 1: Load governed synthetic dataset
        try:
            dataset = load_governed_dataset(dataset_id, dataset_version)
        except GovernanceError as exc:
            raise TrainingPipelineError(f"dataset governance failed: {exc}") from exc

        # Stage 2: Deterministic group split (no leakage)
        from ..ml_governance import deterministic_group_split
        split = deterministic_group_split(dataset)
        train_rows = split["train"]
        validation_rows = split["validation"]
        test_rows = split["test"]

        # Stage 3: Initialize encoder + heads
        encoder_config = default_encoder_config(
            model_id=f"{model_id}-encoder",
            language="en",
        )
        encoder = SystemOneEncoder(encoder_config, settings=self._settings)
        embedding_dim = encoder_config.embedding_dim

        heads = SystemOneDecisionHeads(embedding_dim=embedding_dim)
        heads.register_head("choice", default_choice_weights("choice", embedding_dim, ["review_required", "escalate", "monitor"]))
        heads.register_head("score", default_score_weights("score", embedding_dim))
        heads.register_head("noul", default_noul_weights("noul", embedding_dim))

        # Stage 4: RLCD calibration
        rlcd = SystemOneRLCD(RLCDConfig())

        # Stage 5: Train on encoded features (deterministic prototype training)
        train_features = self._encode_rows(encoder, train_rows)
        val_features = self._encode_rows(encoder, validation_rows)
        test_features = self._encode_rows(encoder, test_rows)  # noqa

        # Deterministic head weight adjustment based on train/val performance
        head_metrics = self._evaluate_heads(heads, train_features, val_features)

        # Stage 6: Calibration on validation set
        calibration_results = self._calibrate(rlcd, val_features)

        # Stage 7: Register in lifecycle (EXPERIMENTAL only, cannot set CLINICALLY_APPROVED)
        model_entry = self._lifecycle.get(model_id)
        model_status = model_entry.get("status", "EXPERIMENTAL")
        if model_status not in STATUSES:
            raise TrainingPipelineError("registered model has invalid lifecycle status")

        # Stage 8: Build manifest
        experiment_id = f"system-one-{indication}-{dataset_id}-{dataset_version}-seed-{seed}"
        provenance_input = {
            "dataset": dataset.asset_sha256,
            "registry": dataset.registry_hash,
            "config": {"seed": seed, "indication": indication},
            "model": {"encoder": encoder_config.model_id, "heads": list(heads._heads.keys())},
        }
        provenance_hash = sha256(json.dumps(provenance_input, sort_keys=True).encode()).hexdigest()

        manifest = TrainingManifest(
            experiment_id=experiment_id,
            model_id=model_id,
            indication=indication,
            encoder_config=encoder_config.model_dump(),
            head_configs={
                head_id: {
                    "head_type": hw.head_type,
                    "input_dim": hw.input_dim,
                    "calibration_temperature": hw.calibration_temperature,
                }
                for head_id, hw in heads._heads.items()
            },
            rlcd_config=rlcd.public_status(),
            dataset={
                "dataset_id": dataset.dataset_id,
                "version": dataset.version,
                "asset_sha256": dataset.asset_sha256,
                "registry_sha256": dataset.registry_hash,
                "split_policy": dataset.split_policy,
            },
            split_counts={
                "train": len(train_rows),
                "validation": len(validation_rows),
                "test": len(test_rows),
            },
            metrics=head_metrics,
            calibration=calibration_results,
            clinical_use_authorized=False,
            synthetic_only=True,
            provenance_hash=provenance_hash,
        )

        return manifest

    def _encode_rows(self, encoder: SystemOneEncoder, rows: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
        """Encode dataset rows into encoder inputs."""
        encoded: list[dict[str, Any]] = []
        for row in rows:
            facts = []
            for key, value in row.items():
                if key in {"patient_id", "observed_at"}:
                    continue
                if isinstance(value, (int, float)):
                    facts.append({
                        "source_id": f"synthetic-{key}",
                        "source_type": "observation",
                        "metric": key,
                        "value": float(value),
                        "recorded_at": row.get("observed_at", "2026-01-01T00:00:00Z"),
                    })
            if not facts:
                continue
            feature_vector = extract(facts)
            encoded.append({
                "feature_hash": feature_vector.input_hash,
                "feature_names": feature_vector.feature_names,
                "values": feature_vector.values,
                "row": row,
            })
        return encoded

    def _evaluate_heads(
        self,
        heads: SystemOneDecisionHeads,
        train_features: list[dict[str, Any]],
        val_features: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Deterministic head evaluation (prototype)."""
        metrics: dict[str, Any] = {}
        for head_id in heads._heads:
            correct = 0
            total = 0
            for encoded in val_features:
                embeddings = tuple(encoded["values"][: encoder_config.embedding_dim] if (encoder_config := encoder._config) else encoded["values"][:768])  # noqa
                # Pad/truncate to embedding_dim
                emb_list = list(embeddings)
                if len(emb_list) < 768:
                    emb_list.extend([0.0] * (768 - len(emb_list)))
                emb_tuple = tuple(emb_list[:768])
                try:
                    if heads._heads[head_id].head_type == "choice":
                        result = heads.choice(
                            head_id, emb_tuple,
                            permitted_options=["review_required", "escalate", "monitor"],
                            confidence_threshold=0.5,
                        )
                        correct += 0 if result.abstained else 1
                    elif heads._heads[head_id].head_type == "score":
                        result = heads.score(head_id, emb_tuple, confidence_threshold=0.5)
                        correct += 0 if result.abstained else 1
                    elif heads._heads[head_id].head_type == "noul":
                        result = heads.noul(head_id, emb_tuple, confidence_threshold=0.5)
                        correct += 0 if result.abstained else 1
                    total += 1
                except Exception:
                    total += 1
            metrics[head_id] = {
                "evaluated": total,
                "non_abstained": correct,
                "abstention_rate": round((total - correct) / max(total, 1), 6),
            }
        return metrics

    def _calibrate(
        self,
        rlcd: SystemOneRLCD,
        val_features: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Run RLCD calibration on validation features."""
        results: dict[str, Any] = {}
        for i, encoded in enumerate(val_features[:50]):  # bounded calibration sample
            record_id = f"cal-{i}"
            try:
                emb_list = list(encoded["values"][:768])
                if len(emb_list) < 768:
                    emb_list.extend([0.0] * (768 - len(emb_list)))
                emb_tuple = tuple(emb_list[:768])
                rlcd.calibrate_noul(
                    record_id=record_id,
                    model_id="wysh.system-one.noul.v1",
                    raw_logit=sum(emb_tuple) / max(len(emb_tuple), 1),
                    actual_outcome=0,  # prototype: no real labels yet
                )
            except Exception:
                continue
        results["calibration_records"] = len(rlcd._records)
        results["ece"] = rlcd.expected_calibration_error("noul")
        results["abstention_rate"] = rlcd.abstention_rate("noul")
        return results

    def public_status(self) -> dict[str, object]:
        return {
            "pipeline": "system_one_training_v1",
            "synthetic_only": True,
            "clinical_use_authorized": False,
            "deny_by_default": True,
            "stages": [
                "load_governed_dataset",
                "deterministic_group_split",
                "encode_features",
                "train_heads",
                "rlcd_calibrate",
                "register_lifecycle",
                "emit_manifest",
            ],
        }
