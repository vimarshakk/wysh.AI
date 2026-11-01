"""R12B local-only Orthanc/OHIF/MONAI prototype contracts."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class LocalImagingServiceConfig(BaseModel):
    service: Literal["orthanc", "ohif", "monai"]
    base_url: str = "http://127.0.0.1"
    enabled: bool = False
    synthetic_only: Literal[True] = True
    network_access: Literal["DISABLED", "LOCALHOST_ONLY"] = "LOCALHOST_ONLY"
    request_timeout_ms: int = Field(default=5000, ge=100, le=60000)
    max_concurrent_jobs: int = Field(default=1, ge=1, le=4)
    max_pixels: int = Field(default=16_000_000, ge=1, le=100_000_000)

    @field_validator("base_url")
    @classmethod
    def local_url_only(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("R12 imaging prototypes permit localhost endpoints only")
        return value.rstrip("/")


class ImagingPrototypeManifest(BaseModel):
    orthanc: LocalImagingServiceConfig = LocalImagingServiceConfig(service="orthanc")
    ohif: LocalImagingServiceConfig = LocalImagingServiceConfig(service="ohif")
    monai: LocalImagingServiceConfig = LocalImagingServiceConfig(service="monai")
    model_weights_downloaded: Literal[False] = False
    clinical_use_authorized: Literal[False] = False


def resource_gate(*, width: int, height: int, timeout_ms: int, max_pixels: int = 16_000_000) -> dict[str, object]:
    pixels = width * height
    checks = {"dimensions_positive": width > 0 and height > 0, "pixel_budget": pixels <= max_pixels, "timeout_budget": 100 <= timeout_ms <= 60000}
    return {"status": "PASS" if all(checks.values()) else "ABSTAINED", "checks": checks, "pixels": pixels, "reason": "resource envelope accepted" if all(checks.values()) else "resource limit exceeded"}


def prototype_status(manifest: ImagingPrototypeManifest) -> list[dict[str, object]]:
    return [{"service": item.service, "status": "CONFIGURED_SYNTHETIC_ONLY" if item.enabled else "NOT_CONFIGURED", "network_access": item.network_access, "model_execution": "ABSTAIN"} for item in (manifest.orthanc, manifest.ohif, manifest.monai)]
