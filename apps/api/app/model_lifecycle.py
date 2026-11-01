"""Fail-closed model registry lifecycle for R8E."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .ml_governance import GovernanceError


STATUSES = ("EXPERIMENTAL", "ENGINEERING_VERIFIED", "CLINICAL_REVIEW_PENDING", "CLINICALLY_APPROVED")
REGISTRY_PATH = Path(__file__).parents[3] / "research/models/model-registry-v1.json"


@dataclass
class ModelLifecycleStore:
    registry_path: Path = REGISTRY_PATH
    _registry: dict[str, Any] | None = None

    def _load(self) -> dict[str, Any]:
        if self._registry is not None:
            return self._registry
        try:
            payload = json.loads(self.registry_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise GovernanceError("model registry is unavailable or invalid") from exc
        if payload.get("schema_version") != "r8e-model-registry-v1":
            raise GovernanceError("unsupported model registry schema")
        self._registry = payload
        return payload

    def get(self, model_id: str) -> dict[str, Any]:
        entries = [entry for entry in self._load().get("models", []) if entry.get("model_id") == model_id]
        if len(entries) != 1:
            raise GovernanceError("model is not uniquely registered")
        return entries[0]

    def transition(self, model_id: str, target: str, *, actor: str, reason: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
        if target not in STATUSES:
            raise GovernanceError("unknown model lifecycle status")
        if not actor or not reason:
            raise GovernanceError("actor and reason are required")
        model = self.get(model_id)
        current = model.get("status")
        if current not in STATUSES:
            raise GovernanceError("registered model has invalid lifecycle status")
        if target == "CLINICALLY_APPROVED":
            raise GovernanceError("clinical approval requires an external qualified governance process")
        allowed = {"EXPERIMENTAL": "ENGINEERING_VERIFIED", "ENGINEERING_VERIFIED": "CLINICAL_REVIEW_PENDING", "CLINICAL_REVIEW_PENDING": None}
        if allowed.get(current) != target:
            raise GovernanceError(f"invalid lifecycle transition {current} -> {target}")
        if target == "ENGINEERING_VERIFIED":
            required = {"reproducibility": "PASS", "leakage": "PASS", "dataset_governance": "PASS", "evaluation_report": "PRESENT"}
            if not evidence or any(evidence.get(key) != value for key, value in required.items()):
                raise GovernanceError("engineering verification requires reproducibility, leakage, governance and evaluation evidence")
        if target == "CLINICAL_REVIEW_PENDING" and not actor.startswith("qualified-reviewer:"):
            raise GovernanceError("clinical review pending requires a qualified reviewer identity")
        transition = {"from": current, "to": target, "actor": actor, "reason": reason, "evidence_sha256": sha256(json.dumps(evidence or {}, sort_keys=True).encode()).hexdigest()}
        model.setdefault("history", []).append(transition)
        model["status"] = target
        return model

    def snapshot(self) -> dict[str, Any]:
        return self._load()
