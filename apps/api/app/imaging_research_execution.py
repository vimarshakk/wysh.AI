"""Tiny native synthetic image-processing task for R13C.

This computes pixel integrity and descriptive statistics only. It is not a
diagnostic model and cannot produce clinical findings.
"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SyntheticPixelTask(BaseModel):
    study_id: str = Field(min_length=1, max_length=128)
    patient_id: str = Field(min_length=1, max_length=128)
    modality: Literal["DX", "CT", "MR", "US"]
    width: int = Field(ge=1, le=4096)
    height: int = Field(ge=1, le=4096)
    pixels: list[int] = Field(min_length=1, max_length=1_000_000)
    expected_sha256: str = Field(min_length=64, max_length=64)
    synthetic: Literal[True] = True

    @field_validator("pixels")
    @classmethod
    def pixel_count_and_range(cls, value: list[int], info):
        width, height = info.data.get("width"), info.data.get("height")
        if width and height and len(value) != width * height:
            raise ValueError("pixel count does not match dimensions")
        if any(not 0 <= pixel <= 4095 for pixel in value):
            raise ValueError("pixel value outside bounded synthetic range")
        return value


def execute_synthetic_pixel_task(task: SyntheticPixelTask) -> dict[str, object]:
    canonical = json.dumps(task.pixels, separators=(",", ":")).encode()
    actual_hash = sha256(canonical).hexdigest()
    checks = {"pixel_hash": actual_hash == task.expected_sha256.lower(), "dimensions": len(task.pixels) == task.width * task.height, "patient_synthetic": task.patient_id.startswith("synthetic-")}
    if not all(checks.values()):
        return {"status": "ABSTAINED", "checks": checks, "reason": "synthetic image integrity or subject gate failed", "clinical_use_authorized": False}
    return {"status": "RESEARCH_DESCRIPTIVE", "checks": checks, "statistics": {"minimum": min(task.pixels), "maximum": max(task.pixels), "mean": sum(task.pixels) / len(task.pixels)}, "preprocessing": "none", "model_id": "native-pixel-integrity-v1", "diagnostic_interpretation": False, "clinical_use_authorized": False, "provenance_hash": actual_hash}
