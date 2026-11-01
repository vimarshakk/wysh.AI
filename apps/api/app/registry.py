from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from pydantic import BaseModel, Field

from .config import Settings


class ModelEntry(BaseModel):
    id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    task: str = Field(min_length=1)
    enabled: bool
    clinical_approved: bool


class ModelRegistry(BaseModel):
    schema_version: str
    default_mode: str
    models: list[ModelEntry]


def default_registry_path() -> Path:
    return Path(__file__).parents[3] / "packages" / "contracts" / "model-registry.json"


def load_registry(path: Path | None = None) -> ModelRegistry:
    if path is not None:
        return ModelRegistry.model_validate_json(path.read_text(encoding="utf-8"))
    source_path = default_registry_path()
    if source_path.exists():
        return ModelRegistry.model_validate_json(source_path.read_text(encoding="utf-8"))
    packaged = resources.files("app").joinpath("model-registry.json")
    return ModelRegistry.model_validate_json(packaged.read_text(encoding="utf-8"))


def public_registry(registry: ModelRegistry, settings: Settings) -> dict[str, object]:
    return {
        "schema_version": registry.schema_version,
        "default_mode": registry.default_mode,
        "models": [
            {
                "id": model.id,
                "provider": model.provider,
                "task": model.task,
                "manifest_enabled": model.enabled,
                "clinical_approved": model.clinical_approved,
                "runtime_enabled": model.enabled and model.id in settings.enabled_model_ids,
            }
            for model in registry.models
        ],
    }
