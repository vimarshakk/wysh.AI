"""Stable, provider-neutral capability catalog for all WyshCare applications."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from pydantic import BaseModel, Field


class ApplicationProfile(BaseModel):
    id: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    capabilities: list[str] = Field(min_length=1)
    requires_human_review: bool


class CapabilityCatalog(BaseModel):
    schema_version: str
    product: str
    clinical_use_authorized: bool
    profiles: list[ApplicationProfile]


def load_capability_catalog() -> CapabilityCatalog:
    source = Path(__file__).parents[3] / "packages" / "contracts" / "application-profiles-v1.json"
    if source.exists():
        return CapabilityCatalog.model_validate_json(source.read_text(encoding="utf-8"))
    packaged = resources.files("app").joinpath("application-profiles-v1.json")
    return CapabilityCatalog.model_validate(json.loads(packaged.read_text(encoding="utf-8")))


def public_capabilities(catalog: CapabilityCatalog) -> dict[str, object]:
    return catalog.model_dump(mode="json")
