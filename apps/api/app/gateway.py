"""Policy-aware model gateway with explicit local-first routing."""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Any, TypeVar

from pydantic import BaseModel

from .config import Settings
from .metrics import Metrics
from .providers import InferenceTelemetry, ProviderError, RoutingAttempt, provider_for
from .registry import ModelRegistry, load_registry

T = TypeVar("T", bound=BaseModel)


class ModelGateway:
    def __init__(self, settings: Settings, registry: ModelRegistry | None = None, metrics: Metrics | None = None):
        self.settings = settings
        self.registry = registry or load_registry()
        self.metrics = metrics

    def model_id_for(self, provider_name: str) -> str:
        if provider_name == "gemini":
            return self.settings.gemini_model
        if provider_name == "medgemma":
            return self.settings.medgemma_model
        if provider_name in {"openai-compatible", "vllm", "llama.cpp"}:
            return self.settings.openai_compatible_model or "unconfigured"
        return provider_name

    def infer(self, requested_provider: str, prompt: str, output_schema: type[T], *, system_prompt: str | None = None) -> tuple[T, InferenceTelemetry]:
        if self.settings.environment != "development":
            raise ProviderError("gateway", "production_inference_disabled", "model inference is disabled outside isolated development")
        if not self.settings.inference_enabled:
            raise ProviderError("gateway", "inference_disabled", "model inference is disabled by configuration")
        configuration_errors = self.settings.configuration_errors()
        if configuration_errors:
            raise ProviderError("gateway", "invalid_configuration", ";".join(configuration_errors))
        providers = [requested_provider] if requested_provider != "auto" else list(self.settings.model_routing_order)
        errors: list[str] = []
        route_attempts: list[RoutingAttempt] = []
        route_started = time.perf_counter()
        for provider_name in providers:
            if provider_name == "gemini" and not self.settings.allow_cloud_fallback and requested_provider == "auto":
                errors.append("gemini:cloud_fallback_disabled")
                route_attempts.append(RoutingAttempt(provider_name, self.model_id_for(provider_name), "skipped", "cloud_fallback_disabled"))
                continue
            model_id = self.model_id_for(provider_name)
            manifest = next((item for item in self.registry.models if item.id == model_id), None)
            if manifest is None or not manifest.enabled or model_id not in self.settings.enabled_model_ids:
                errors.append(f"{provider_name}:model_not_enabled")
                route_attempts.append(RoutingAttempt(provider_name, model_id, "skipped", "model_not_enabled"))
                if requested_provider != "auto":
                    raise ProviderError(provider_name, "model_not_enabled", "model is not both manifest-enabled and runtime-allowlisted")
                continue
            try:
                provider = provider_for(self.settings, provider_name)
                started = time.perf_counter()
                output, telemetry = provider.infer(prompt, output_schema, system_prompt=system_prompt)
                route_attempts.append(RoutingAttempt(provider_name, model_id, "success", None, int((time.perf_counter() - started) * 1000)))
                if self.metrics is not None:
                    self.metrics.observe_provider(provider_name, "success", int((time.perf_counter() - started) * 1000))
                return output, replace(telemetry, route_attempts=tuple(route_attempts))
            except ProviderError as exc:
                route_attempts.append(RoutingAttempt(provider_name, model_id, "failure", exc.classification, int((time.perf_counter() - started) * 1000)))
                if self.metrics is not None:
                    self.metrics.observe_provider(provider_name, "failure", int((time.perf_counter() - started) * 1000))
                errors.append(f"{exc.provider}:{exc.classification}")
                if requested_provider != "auto":
                    raise
        failed_telemetry = InferenceTelemetry(
            request_id="route-" + str(int(route_started * 1000000)),
            provider="gateway",
            model="unresolved",
            status="route_failed",
            latency_ms=int((time.perf_counter() - route_started) * 1000),
            route_attempts=tuple(route_attempts),
        )
        raise ProviderError("gateway", "all_providers_failed", ";".join(errors) or "no providers configured", telemetry=failed_telemetry)
