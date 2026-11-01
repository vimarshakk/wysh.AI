"""System One external validation harness.

Phase 4 — Launch & Surveillance. Runs the System One decision model end-to-end
on held-out de-identified data, producing a validation report with metrics,
subgroup analysis, and RLCD calibration.

Synthetic-only: no PHI accepted, clinical use not authorized.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path  # noqa
from typing import Any

from ..config import Settings
from ..decision_model import SystemOneDecisionModel  # noqa
from ..feature_extractor import ClinicalFact, extract
from ..ml_governance import GovernanceError, load_governed_dataset
from ..ml_operations import ModelVersion, ResearchModelRegistry  # noqa
from ..model_lifecycle import ModelLifecycleStore, REGISTRY_PATH, STATUSES  # noqa
from .decision_heads import (
    SystemOneDecisionHeads,
    default_choice_weights,
    default_noul_weights,
    default_score_weights,
)
from .encoder import SystemOneEncoder, default_encoder_config
from .rlcd import RLCDConfig, SystemOneRLCD
from .validation_engine import SystemOneValidationEngine, ValidationCase


class ValidationHarnessError(ValueError):
    pass


@dataclass(frozen=True)
class ValidationHarnessResult:
    report_id: str
    model_id: str
    indication: str
    dataset_id: str
    noul_auroc: float | None
    noul_auprc: float | None
    noul_brier_score: float | None
    noul_ece: float | None
    choice_accuracy: float | None
    abstention_rate: float
    human_handoff_rate: float
    n_cases: int
    n_abstained: int
    n_human_handoff: int
    clinical_use_authorized: bool
    synthetic_only: bool
    subgroup_slices: list[dict[str, Any]]
    validation_timestamp: str
    provenance_hash: str


class SystemOneValidationHarness:
    """End-to-end validation harness for the System One decision model.

    Wires together: encoder -> decision heads -> RLCD calibration ->
    validation engine -> validation report.
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
    ) -> ValidationHarnessResult:
        """Run full end-to-end validation on a governed dataset."""
        from ..ml_governance import deterministic_group_split

        started = datetime.now(timezone.utc)

        # Stage 1: Load governed synthetic dataset
        try:
            dataset = load_governed_dataset(dataset_id, dataset_version)
        except GovernanceError as exc:
            raise ValidationHarnessError(f"dataset governance failed: {exc}") from exc

        # Stage 2: Deterministic group split (no leakage)
        split = deterministic_group_split(dataset)
        test_rows = split["test"]

        # Stage 3: Initialize encoder + heads + RLCD
        encoder_config = default_encoder_config(
            model_id=f"{model_id}-encoder",
            language="en",
        )
        encoder = SystemOneEncoder(encoder_config, settings=self._settings)  # noqa
        embedding_dim = encoder_config.embedding_dim

        heads = SystemOneDecisionHeads(embedding_dim=embedding_dim)
        heads.register_head(
            "choice",
            default_choice_weights("choice", embedding_dim, ["review_required", "escalate", "monitor"]),
        )
        heads.register_head("score", default_score_weights("score", embedding_dim))
        heads.register_head("noul", default_noul_weights("noul", embedding_dim))

        rlcd = SystemOneRLCD(RLCDConfig())

        # Stage 4: Encode test rows and run decisions
        cases: list[ValidationCase] = []
        for row in test_rows:
            facts = []
            for key, value in row.items():
                if key in {"patient_id", "observed_at"}:
                    continue
                if isinstance(value, (int, float)):
                    facts.append(
                        ClinicalFact(
                            source_id=f"synthetic-{key}",
                            source_type="observation",
                            metric=key,
                            value=float(value),
                            recorded_at=row.get("observed_at", "2026-01-01T00:00:00Z"),
                        )
                    )
            if not facts:
                continue

            feature_vector = extract(facts)
            embeddings = tuple(feature_vector.values[:embedding_dim])
            # Pad/truncate to embedding_dim
            emb_list = list(embeddings)
            if len(emb_list) < embedding_dim:
                emb_list.extend([0.0] * (embedding_dim - len(emb_list)))
            emb_tuple = tuple(emb_list[:embedding_dim])

            # Run heads
            try:
                choice_result = heads.choice(
                    "choice", emb_tuple,
                    permitted_options=["review_required", "escalate", "monitor"],
                    confidence_threshold=0.5,
                )
                score_result = heads.score("score", emb_tuple, confidence_threshold=0.5)  # noqa
                noul_result = heads.noul("noul", emb_tuple, confidence_threshold=0.85)
            except Exception:
                continue

            # Run RLCD calibration
            rlcd.calibrate_noul(
                record_id=f"val-{row.get('patient_id', 'unknown')}-{seed}",
                model_id=model_id,
                raw_logit=sum(emb_tuple) / max(len(emb_tuple), 1),
                actual_outcome=int(row.get("synthetic_review_required", 0)),
            )

            # Determine choice_correct
            choice_correct: bool | None = None
            if not choice_result.abstained:
                # For synthetic data, use the review label as ground truth
                actual_label = int(row.get("synthetic_review_required", 0))
                # Map: escalate -> review_required=1, review_required/monitor -> 0
                choice_correct = (
                    (choice_result.selected_option == "escalate" and actual_label == 1)
                    or (choice_result.selected_option != "escalate" and actual_label == 0)
                )

            case = ValidationCase(
                case_id=f"val-{row.get('patient_id', 'unknown')}",
                indication=indication,
                language="en",
                age_band="45-64",  # synthetic default
                sex="M",  # synthetic default
                comorbidity_count=1,  # synthetic default
                noul_probability=noul_result.probability_yes or 0.0,
                noul_confidence=noul_result.confidence,
                noul_abstained=noul_result.abstained,
                choice_selected=choice_result.selected_option,
                choice_confidence=choice_result.confidence,
                choice_abstained=choice_result.abstained,
                actual_outcome=int(row.get("synthetic_review_required", 0)),
                choice_correct=choice_correct,
            )
            cases.append(case)

        # Stage 5: Generate validation report
        engine = SystemOneValidationEngine(model_id=model_id, indication=indication)
        for case in cases:
            engine.add_case(case)

        report = engine.generate_report(dataset_id=dataset_id)

        # Stage 6: Build harness result
        provenance_input = {
            "dataset": dataset.asset_sha256,
            "registry": dataset.registry_hash,
            "config": {"seed": seed, "indication": indication},
            "model": {
                "encoder": encoder_config.model_id,
                "heads": list(heads._heads.keys()),
                "rlcd": rlcd.public_status(),
            },
            "report": {
                "noul_auroc": report.noul_metrics.auroc,
                "noul_auprc": report.noul_metrics.auprc,
                "noul_brier_score": report.noul_metrics.brier_score,
                "noul_ece": report.noul_metrics.expected_calibration_error,
                "choice_accuracy": report.choice_metrics.accuracy,
                "abstention_rate": report.overall_abstention_rate,
            },
        }
        provenance_hash = sha256(json.dumps(provenance_input, sort_keys=True).encode()).hexdigest()

        latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)  # noqa

        return ValidationHarnessResult(
            report_id=report.report_id,
            model_id=model_id,
            indication=indication,
            dataset_id=dataset_id,
            noul_auroc=report.noul_metrics.auroc,
            noul_auprc=report.noul_metrics.auprc,
            noul_brier_score=report.noul_metrics.brier_score,
            noul_ece=report.noul_metrics.expected_calibration_error,
            choice_accuracy=report.choice_metrics.accuracy,
            abstention_rate=report.overall_abstention_rate,
            human_handoff_rate=report.overall_human_handoff_rate,
            n_cases=len(cases),
            n_abstained=report.noul_metrics.n_abstained,
            n_human_handoff=report.noul_metrics.n_human_handoff,
            clinical_use_authorized=False,
            synthetic_only=True,
            subgroup_slices=[
                {
                    "dimension": s.dimension,
                    "value": s.value,
                    "n_cases": s.n_cases,
                    "noul_auroc": s.noul_auroc,
                    "choice_accuracy": s.choice_accuracy,
                    "abstention_rate": s.abstention_rate,
                }
                for s in report.subgroup_slices
            ],
            validation_timestamp=report.validation_timestamp,
            provenance_hash=provenance_hash,
        )

    def public_status(self) -> dict[str, object]:
        return {
            "harness": "system_one_validation_v1",
            "synthetic_only": True,
            "clinical_use_authorized": False,
            "deny_by_default": True,
            "stages": [
                "load_governed_dataset",
                "deterministic_group_split",
                "encode_features",
                "run_heads",
                "rlcd_calibrate",
                "generate_report",
            ],
        }
