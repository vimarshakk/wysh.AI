"""Measure bounded repeated real-local MedGemma inference for R14E."""

from __future__ import annotations

import json
import os
import statistics
import time
from dataclasses import replace
from pathlib import Path
import sys

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.clinical_orchestration import ClinicalExplanation, _model_safety
from app.config import Settings
from app.gateway import ModelGateway
from app.providers import MEDGEMMA_MAX_OUTPUT_TOKENS, MedGemmaProvider, ProviderError
from app.registry import load_registry


def main() -> int:
    requested_model = os.environ.get("MEDGEMMA_MODEL", "medgemma:latest")
    base = Settings.from_sources()
    settings = replace(base, inference_enabled=True, model_routing_order=("medgemma",), enabled_model_ids=frozenset({requested_model}), medgemma_model=requested_model, provider_timeout_ms=max(base.provider_timeout_ms, 60000), provider_max_retries=0)
    output = ROOT / "artifacts/r14-test-evidence/r14-reliability.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if not MedGemmaProvider(settings).ready():
        report = {"schema_version": "r14-reliability-v1", "status": "BLOCKED", "reason": "local MedGemma runtime/model is not ready", "synthetic_only": True}
        output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
        return 2

    gateway = ModelGateway(settings, load_registry())
    latencies: list[int] = []
    results = []
    for index in range(3):
        started = time.perf_counter()
        try:
            explanation, telemetry = gateway.infer(
                "medgemma",
                json.dumps({"task": "safe synthetic reliability probe", "user_text": "Summarize only the supplied synthetic evidence and abstain if it is insufficient.", "evidence_refs": ["synthetic-reliability-1"]}),
                ClinicalExplanation,
                system_prompt="Return one concise JSON object only. State limitations, remain draft-only, and never diagnose or prescribe.",
            )
            safety = _model_safety(explanation, {"synthetic-reliability-1"})
            elapsed = int((time.perf_counter() - started) * 1000)
            latencies.append(elapsed)
            results.append({"iteration": index + 1, "status": safety.status, "schema_validated": telemetry.schema_validated, "latency_ms": elapsed, "model": telemetry.model})
        except ProviderError as exc:
            results.append({"iteration": index + 1, "status": "PROVIDER_ERROR", "classification": exc.classification})

    successful = [item["latency_ms"] for item in results if item.get("schema_validated")]
    report = {
        "schema_version": "r14-reliability-v1",
        "status": "PASS" if len(successful) == 3 else "FAIL",
        "synthetic_only": True,
        "model_id": requested_model,
        "iterations": 3,
        "results": results,
        "latency_ms": {"min": min(successful) if successful else None, "median": statistics.median(successful) if successful else None, "max": max(successful) if successful else None},
        "resource_contract": {"timeout_ms": settings.provider_timeout_ms, "max_output_tokens": MEDGEMMA_MAX_OUTPUT_TOKENS, "retries": settings.provider_max_retries, "fixture_fallback": False},
        "clinical_use_authorized": False,
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
