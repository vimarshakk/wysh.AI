"""Run opt-in real provider probes and write only sanitized evidence."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from app.config import Settings
from app.decision import DecisionModelOutput
from app.providers import GeminiProvider, MedGemmaProvider, OpenAICompatibleProvider, ProviderError
from app.trion import TrionClient, TrionError


def run(name: str, model: str, call):
    started = time.perf_counter()
    try:
        _, telemetry = call()
        return {"integration": name, "status": "PASS", "model_id": model, "latency_ms": telemetry.latency_ms, "schema_validated": telemetry.schema_validated}
    except ProviderError as exc:
        return {"integration": name, "status": "BLOCKED" if exc.classification in {"invalid_credentials", "unavailable", "timeout"} else "FAIL", "model_id": model, "error": exc.classification, "latency_ms": int((time.perf_counter() - started) * 1000)}


def run_trion(settings: Settings) -> dict[str, object]:
    started = time.perf_counter()
    model = settings.trion_model or "unconfigured"
    if not settings.trion_enabled or not settings.trion_base_url or not settings.trion_api_key:
        return {"integration": "trion", "status": "BLOCKED", "model_id": model, "error": "endpoint_unavailable_or_unconfigured", "latency_ms": 0}
    try:
        result = TrionClient(settings).execute(
            {"schemaVersion": 1, "documentId": "synthetic-real-smoke", "facts": []},
            correlation_id="synthetic-real-smoke",
            idempotency_key="synthetic-real-smoke",
        )
        return {"integration": "trion", "status": "PASS", "model_id": result.payload.get("model") or model, "response_schema": result.payload.get("schemaVersion"), "latency_ms": int((time.perf_counter() - started) * 1000)}
    except TrionError as exc:
        message = str(exc).lower()
        if "timed out" in message:
            error = "timeout"
        elif "unavailable" in message:
            error = "endpoint_unavailable"
        elif "invalid json" in message or "schema" in message:
            error = "invalid_response"
        else:
            error = "http_error"
        return {"integration": "trion", "status": "BLOCKED" if error in {"timeout", "endpoint_unavailable"} else "FAIL", "model_id": model, "error": error, "latency_ms": int((time.perf_counter() - started) * 1000)}


def main() -> int:
    settings = Settings.from_sources()
    evidence = [
        run("gemini", settings.gemini_model, lambda: GeminiProvider(settings).infer("Return a synthetic workflow routing decision for an intake labelled routine.", DecisionModelOutput)),
    ]
    medgemma = MedGemmaProvider(settings)
    if medgemma.ready():
        evidence.append(run("medgemma", settings.medgemma_model, lambda: medgemma.infer("Return a synthetic workflow routing decision for an intake labelled routine.", DecisionModelOutput)))
    else:
        evidence.append({"integration": "medgemma", "status": "BLOCKED", "model_id": settings.medgemma_model, "error": "endpoint_unavailable"})
    compatible = OpenAICompatibleProvider(settings)
    if compatible.ready():
        evidence.append(run("openai-compatible", settings.openai_compatible_model or "unconfigured", lambda: compatible.infer("Return a synthetic workflow routing decision for an intake labelled routine.", DecisionModelOutput)))
    else:
        evidence.append({"integration": "openai-compatible", "status": "BLOCKED", "model_id": settings.openai_compatible_model or "unconfigured", "error": "endpoint_unavailable_or_unconfigured"})
    evidence.append(run_trion(settings))
    output = Path(__file__).parents[3] / "artifacts" / "r1-test-evidence" / "real-provider-smoke.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"synthetic_only": True, "evidence": evidence}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), "evidence": evidence}, indent=2))
    return 0 if all(item["status"] in {"PASS", "BLOCKED"} for item in evidence) else 1


if __name__ == "__main__":
    sys.exit(main())
