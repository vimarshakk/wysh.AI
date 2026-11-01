"""Explicit, allowlisted configuration for the wysh.AI service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


ALLOWED_ENV_KEYS = frozenset(
    {
        "WMI_ENV",
        "WMI_INFERENCE_ENABLED",
        "WMI_REQUIRE_GATEWAY_AUTH",
        "MODEL_ROUTING_ORDER",
        "ALLOW_CLOUD_FALLBACK",
        "MODEL_ENABLED_IDS",
        "SERVICE_TOKEN_SECRET",
        "SERVICE_TOKEN_ISSUER",
        "SERVICE_TOKEN_AUDIENCE",
        "SERVICE_TOKEN_ALGORITHM",
        "SERVICE_TOKEN_JWKS_URL",
        "SERVICE_TOKEN_JWKS_CACHE_TTL_SECONDS",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "GEMINI_API_BASE",
        "MEDGEMMA_BASE_URL",
        "MEDGEMMA_MODEL",
        "MEDGEMMA_MODEL_VERSION",
        "OLLAMA_HOST",
        "OLLAMA_URL",
        "OPENAI_COMPATIBLE_BASE_URL",
        "OPENAI_COMPATIBLE_API_KEY",
        "OPENAI_COMPATIBLE_MODEL",
        "OPENAI_COMPATIBLE_PATH",
        "TRION_ENABLED",
        "TRION_BASE_URL",
        "TRION_API_KEY",
        "TRION_MODEL",
        "TRION_PATH",
        "TRION_TIMEOUT_MS",
        "PROVIDER_TIMEOUT_MS",
        "PROVIDER_MAX_RETRIES",
    }
)


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key not in ALLOWED_ENV_KEYS:
            continue
        values[key] = value.strip().strip("\"'")
    return values


@dataclass(frozen=True)
class Settings:
    environment: str = "development"
    inference_enabled: bool = False
    require_gateway_auth: bool = False
    service_token_secret: str | None = None
    service_token_issuer: str = "wyshcare"
    service_token_audience: str = "wysh-ai"
    service_token_algorithm: str = "HS256"
    service_token_jwks_url: str | None = None
    service_token_jwks_cache_ttl_seconds: int = 300
    model_routing_order: tuple[str, ...] = ("medgemma", "openai-compatible", "gemini")
    allow_cloud_fallback: bool = False
    enabled_model_ids: frozenset[str] = frozenset()
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_api_base: str = "https://generativelanguage.googleapis.com/v1beta"
    medgemma_base_url: str = "http://127.0.0.1:11434"
    medgemma_model: str = "medgemma:4b"
    medgemma_model_version: str | None = None
    openai_compatible_base_url: str | None = None
    openai_compatible_api_key: str | None = None
    openai_compatible_model: str | None = None
    openai_compatible_path: str = "/v1/chat/completions"
    trion_enabled: bool = False
    trion_base_url: str | None = None
    trion_api_key: str | None = None
    trion_model: str | None = None
    trion_path: str = "/v1/clinical/fhir-draft"
    trion_timeout_ms: int = 5000
    provider_timeout_ms: int = 30000
    provider_max_retries: int = 2

    @classmethod
    def from_sources(cls, env_file: str | None = None) -> "Settings":
        file_values = _parse_env_file(Path(env_file)) if env_file else {}
        values = {key: os.environ[key] for key in ALLOWED_ENV_KEYS if key in os.environ}
        values.update(file_values)

        def boolean(name: str, default: bool) -> bool:
            return values.get(name, str(default)).lower() in {"1", "true", "yes", "on"}

        def integer(name: str, default: int) -> int:
            try:
                return max(1, int(values.get(name, default)))
            except (TypeError, ValueError):
                return default

        ollama_url = values.get("OLLAMA_HOST") or values.get("OLLAMA_URL")
        routing_order = tuple(item.strip() for item in values.get("MODEL_ROUTING_ORDER", "medgemma,openai-compatible,gemini").split(",") if item.strip())
        enabled_model_ids = frozenset(item.strip() for item in values.get("MODEL_ENABLED_IDS", "").split(",") if item.strip())
        return cls(
            environment=values.get("WMI_ENV", "development"),
            inference_enabled=boolean("WMI_INFERENCE_ENABLED", False),
            require_gateway_auth=boolean("WMI_REQUIRE_GATEWAY_AUTH", False),
            service_token_secret=values.get("SERVICE_TOKEN_SECRET") or None,
            service_token_issuer=values.get("SERVICE_TOKEN_ISSUER", "wyshcare"),
            service_token_audience=values.get("SERVICE_TOKEN_AUDIENCE", "wysh-ai"),
            service_token_algorithm=values.get("SERVICE_TOKEN_ALGORITHM", "HS256"),
            service_token_jwks_url=values.get("SERVICE_TOKEN_JWKS_URL") or None,
            service_token_jwks_cache_ttl_seconds=integer("SERVICE_TOKEN_JWKS_CACHE_TTL_SECONDS", 300),
            model_routing_order=routing_order or ("medgemma", "openai-compatible", "gemini"),
            allow_cloud_fallback=boolean("ALLOW_CLOUD_FALLBACK", False),
            enabled_model_ids=enabled_model_ids,
            gemini_api_key=values.get("GEMINI_API_KEY") or None,
            gemini_model=values.get("GEMINI_MODEL", "gemini-2.5-flash"),
            gemini_api_base=values.get("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta").rstrip("/"),
            medgemma_base_url=(values.get("MEDGEMMA_BASE_URL") or ollama_url or "http://127.0.0.1:11434").rstrip("/"),
            medgemma_model=values.get("MEDGEMMA_MODEL", "medgemma:4b"),
            medgemma_model_version=values.get("MEDGEMMA_MODEL_VERSION") or None,
            openai_compatible_base_url=values.get("OPENAI_COMPATIBLE_BASE_URL", "").rstrip("/") or None,
            openai_compatible_api_key=values.get("OPENAI_COMPATIBLE_API_KEY") or None,
            openai_compatible_model=values.get("OPENAI_COMPATIBLE_MODEL") or None,
            openai_compatible_path=values.get("OPENAI_COMPATIBLE_PATH", "/v1/chat/completions"),
            trion_enabled=boolean("TRION_ENABLED", False),
            trion_base_url=values.get("TRION_BASE_URL") or None,
            trion_api_key=values.get("TRION_API_KEY") or None,
            trion_model=values.get("TRION_MODEL") or None,
            trion_path=values.get("TRION_PATH", "/v1/clinical/fhir-draft"),
            trion_timeout_ms=integer("TRION_TIMEOUT_MS", 5000),
            provider_timeout_ms=integer("PROVIDER_TIMEOUT_MS", 30000),
            provider_max_retries=min(integer("PROVIDER_MAX_RETRIES", 2), 5),
        )

    def provider_public_status(self) -> dict[str, object]:
        return {
            "inference_enabled": self.inference_enabled,
            "gateway_auth_required": self.require_gateway_auth,
            "gateway_auth_configured": bool(self.service_token_secret),
            "model_routing_order": list(self.model_routing_order),
            "cloud_fallback_enabled": self.allow_cloud_fallback,
            "enabled_model_ids": sorted(self.enabled_model_ids),
            "gemini_configured": bool(self.gemini_api_key),
            "gemini_model": self.gemini_model,
            "medgemma_endpoint_configured": bool(self.medgemma_base_url),
            "medgemma_model": self.medgemma_model,
            "openai_compatible_configured": bool(self.openai_compatible_base_url and self.openai_compatible_model),
            "openai_compatible_model": self.openai_compatible_model,
            "trion_enabled": self.trion_enabled,
            "trion_configured": bool(self.trion_base_url and self.trion_api_key),
            "endpoint_configuration_valid": not self.configuration_errors(),
        }

    def configuration_errors(self) -> list[str]:
        """Return redacted endpoint errors; never include URL values or secrets."""
        errors: list[str] = []
        for name, value in (("GEMINI_API_BASE", self.gemini_api_base), ("MEDGEMMA_BASE_URL", self.medgemma_base_url), ("OPENAI_COMPATIBLE_BASE_URL", self.openai_compatible_base_url), ("TRION_BASE_URL", self.trion_base_url), ("SERVICE_TOKEN_JWKS_URL", self.service_token_jwks_url)):
            if not value:
                continue
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                errors.append(f"{name}: unsupported endpoint URL")
            elif parsed.username or parsed.password:
                errors.append(f"{name}: embedded endpoint credentials are not permitted")
            elif parsed.query or parsed.fragment:
                errors.append(f"{name}: query strings and fragments are not permitted")
        for name, value in (("OPENAI_COMPATIBLE_PATH", self.openai_compatible_path), ("TRION_PATH", self.trion_path)):
            if not value.startswith("/") or "://" in value or "\\" in value or ".." in value:
                errors.append(f"{name}: endpoint path must be a relative path")
        supported_routes = {"gemini", "medgemma", "openai-compatible", "vllm", "llama.cpp"}
        unknown_routes = sorted(set(self.model_routing_order) - supported_routes)
        if unknown_routes:
            errors.append("MODEL_ROUTING_ORDER: unsupported provider name")
        if not 1 <= self.provider_timeout_ms <= 120_000:
            errors.append("PROVIDER_TIMEOUT_MS: outside bounded resource contract")
        if not 1 <= self.trion_timeout_ms <= 120_000:
            errors.append("TRION_TIMEOUT_MS: outside bounded resource contract")
        if not 0 <= self.provider_max_retries <= 5:
            errors.append("PROVIDER_MAX_RETRIES: outside bounded retry contract")
        return errors
