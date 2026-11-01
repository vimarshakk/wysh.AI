"""Provider adapters with bounded retries, typed parsing, and redacted errors."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from .config import Settings

T = TypeVar("T", bound=BaseModel)
MAX_PROVIDER_OUTPUT_TOKENS = 512
# Retained as a named compatibility constant for the R14/R7D evidence.
MEDGEMMA_MAX_OUTPUT_TOKENS = MAX_PROVIDER_OUTPUT_TOKENS
MAX_PROVIDER_REQUEST_BYTES = 64 * 1024
MAX_PROVIDER_RESPONSE_BYTES = 1024 * 1024


@dataclass(frozen=True)
class RoutingAttempt:
    provider: str
    model: str
    status: str
    reason: str | None = None
    latency_ms: int = 0


@dataclass(frozen=True)
class InferenceTelemetry:
    request_id: str
    provider: str
    model: str
    status: str
    latency_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    schema_validated: bool = False
    route_attempts: tuple[RoutingAttempt, ...] = ()
    retry_count: int = 0


class ProviderError(RuntimeError):
    def __init__(self, provider: str, classification: str, message: str, *, telemetry: InferenceTelemetry | None = None):
        super().__init__(f"{provider}:{classification}: {message}")
        self.provider = provider
        self.classification = classification
        self.telemetry = telemetry


def _json_request(url: str, payload: dict[str, Any], headers: dict[str, str], timeout_ms: int) -> tuple[int, dict[str, Any]]:
    encoded_payload = json.dumps(payload).encode("utf-8")
    if len(encoded_payload) > MAX_PROVIDER_REQUEST_BYTES:
        raise ProviderError("http", "request_too_large", "provider request exceeds the bounded payload limit")
    request = urllib.request.Request(
        url,
        data=encoded_payload,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_ms / 1000) as response:
            raw_bytes = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
            if len(raw_bytes) > MAX_PROVIDER_RESPONSE_BYTES:
                raise ProviderError("http", "response_too_large", "provider response exceeds the bounded payload limit")
            raw = raw_bytes.decode("utf-8")
            return response.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        # Never include the response body: providers may echo prompts or secrets.
        raise ProviderError("http", "http_error", f"HTTP {exc.code}") from None
    except TimeoutError:
        raise ProviderError("http", "timeout", "request timed out") from None
    except urllib.error.URLError:
        raise ProviderError("http", "unavailable", "provider endpoint unavailable") from None
    except json.JSONDecodeError:
        raise ProviderError("http", "invalid_response", "provider returned invalid JSON") from None


class GeminiProvider:
    name = "gemini"

    def __init__(self, settings: Settings):
        self.settings = settings

    def infer(self, prompt: str, output_schema: type[T], *, system_prompt: str | None = None) -> tuple[T, InferenceTelemetry]:
        if not self.settings.gemini_api_key:
            raise ProviderError(self.name, "invalid_credentials", "GEMINI_API_KEY is not configured")
        schema = output_schema.model_json_schema()
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": schema, "maxOutputTokens": MAX_PROVIDER_OUTPUT_TOKENS},
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        url = f"{self.settings.gemini_api_base}/models/{self.settings.gemini_model}:generateContent"
        return _infer_with_retries(self.name, self.settings.gemini_model, self.settings, output_schema, url, payload, {"x-goog-api-key": self.settings.gemini_api_key}, self._extract)

    @staticmethod
    def _extract(data: dict[str, Any]) -> tuple[str, int | None, int | None]:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata", {})
        return text, usage.get("promptTokenCount"), usage.get("candidatesTokenCount")


class MedGemmaProvider:
    name = "medgemma"

    def __init__(self, settings: Settings):
        self.settings = settings

    def ready(self) -> bool:
        request = urllib.request.Request(f"{self.settings.medgemma_base_url}/api/tags", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.settings.provider_timeout_ms / 1000) as response:
                if response.status != 200:
                    return False
                raw_inventory = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
                if len(raw_inventory) > MAX_PROVIDER_RESPONSE_BYTES:
                    return False
                body = json.loads(raw_inventory.decode("utf-8"))
                return any(item.get("name") == self.settings.medgemma_model or item.get("model") == self.settings.medgemma_model for item in body.get("models", []))
        except (OSError, TimeoutError, json.JSONDecodeError, AttributeError):
            return False

    def infer(self, prompt: str, output_schema: type[T], *, system_prompt: str | None = None) -> tuple[T, InferenceTelemetry]:
        payload: dict[str, Any] = {
            "model": self.settings.medgemma_model,
            "messages": ([{"role": "system", "content": system_prompt}] if system_prompt else []) + [{"role": "user", "content": prompt}],
            "format": output_schema.model_json_schema(),
            "stream": False,
            # Structured clinical summaries are intentionally short. Bounding
            # generated tokens prevents a local model from holding the request
            # open while producing an unbounded explanation.
            # MedGemma can spend the whole short budget repeating a refusal
            # before emitting the remaining required JSON keys.  Keep the
            # response bounded, but leave enough room for the typed safety
            # envelope to complete; malformed/truncated output still fails
            # closed in _infer_with_retries.
            "options": {"temperature": 0, "num_predict": MEDGEMMA_MAX_OUTPUT_TOKENS},
        }
        url = f"{self.settings.medgemma_base_url}/api/chat"
        return _infer_with_retries(self.name, self.settings.medgemma_model, self.settings, output_schema, url, payload, {}, self._extract)

    @staticmethod
    def _extract(data: dict[str, Any]) -> tuple[str, int | None, int | None]:
        message = data.get("message", {})
        return message["content"], data.get("prompt_eval_count"), data.get("eval_count")


class OpenAICompatibleProvider:
    """Adapter for vLLM, llama.cpp servers, and other OpenAI-compatible runtimes."""

    name = "openai-compatible"

    def __init__(self, settings: Settings):
        self.settings = settings

    def ready(self) -> bool:
        if not self.settings.openai_compatible_base_url or not self.settings.openai_compatible_model:
            return False
        request = urllib.request.Request(
            f"{self.settings.openai_compatible_base_url}/v1/models",
            headers={"Authorization": f"Bearer {self.settings.openai_compatible_api_key}"} if self.settings.openai_compatible_api_key else {},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.settings.provider_timeout_ms / 1000) as response:
                if response.status != 200:
                    return False
                raw_inventory = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
                if len(raw_inventory) > MAX_PROVIDER_RESPONSE_BYTES:
                    return False
                body = json.loads(raw_inventory.decode("utf-8"))
                model_ids = {str(item.get("id")) for item in body.get("data", []) if isinstance(item, dict) and item.get("id")}
                return self.settings.openai_compatible_model in model_ids
        except (OSError, TimeoutError, json.JSONDecodeError, AttributeError, TypeError):
            return False

    def infer(self, prompt: str, output_schema: type[T], *, system_prompt: str | None = None) -> tuple[T, InferenceTelemetry]:
        if not self.settings.openai_compatible_base_url or not self.settings.openai_compatible_model:
            raise ProviderError(self.name, "not_configured", "OPENAI_COMPATIBLE_BASE_URL and MODEL are required")
        messages = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + [{"role": "user", "content": prompt}]
        schema_name = output_schema.__name__.lower()
        payload = {
            "model": self.settings.openai_compatible_model,
            "messages": messages,
            "temperature": 0,
            "stream": False,
            "max_tokens": MAX_PROVIDER_OUTPUT_TOKENS,
            "response_format": {"type": "json_schema", "json_schema": {"name": schema_name, "strict": True, "schema": output_schema.model_json_schema()}},
        }
        headers = {"Authorization": f"Bearer {self.settings.openai_compatible_api_key}"} if self.settings.openai_compatible_api_key else {}
        url = f"{self.settings.openai_compatible_base_url}{self.settings.openai_compatible_path}"
        return _infer_with_retries(self.name, self.settings.openai_compatible_model, self.settings, output_schema, url, payload, headers, self._extract)

    @staticmethod
    def _extract(data: dict[str, Any]) -> tuple[str, int | None, int | None]:
        message = data["choices"][0]["message"]
        usage = data.get("usage", {})
        return message["content"], usage.get("prompt_tokens"), usage.get("completion_tokens")


def provider_for(settings: Settings, provider: str):
    if provider == "gemini":
        return GeminiProvider(settings)
    if provider == "medgemma":
        return MedGemmaProvider(settings)
    if provider in {"openai-compatible", "vllm", "llama.cpp"}:
        return OpenAICompatibleProvider(settings)
    raise ProviderError(provider, "unsupported_provider", "provider is not enabled")


def _infer_with_retries(
    provider: str,
    model: str,
    settings: Settings,
    output_schema: type[T],
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    extract: Any,
) -> tuple[T, InferenceTelemetry]:
    if len(json.dumps(payload).encode("utf-8")) > MAX_PROVIDER_REQUEST_BYTES:
        raise ProviderError(provider, "request_too_large", "provider request exceeds the bounded payload limit")
    request_id = str(uuid4())
    last_error: ProviderError | None = None
    for attempt in range(settings.provider_max_retries + 1):
        started = time.perf_counter()
        try:
            _, data = _json_request(url, payload, headers, settings.provider_timeout_ms)
            text, prompt_tokens, completion_tokens = extract(data)
            parsed = output_schema.model_validate_json(text)
            telemetry = InferenceTelemetry(request_id, provider, model, "success", int((time.perf_counter() - started) * 1000), prompt_tokens, completion_tokens, True, retry_count=attempt)
            return parsed, telemetry
        except ValidationError:
            raise ProviderError(provider, "schema_validation", "provider output failed schema validation") from None
        except ProviderError as exc:
            last_error = ProviderError(provider, exc.classification, str(exc).split(": ", 2)[-1])
            if exc.classification not in {"timeout", "unavailable", "http_error"} or attempt >= settings.provider_max_retries:
                break
            time.sleep(min(0.05 * (2**attempt), 0.5))
        except (KeyError, TypeError, ValueError):
            raise ProviderError(provider, "invalid_response", "provider response did not contain expected content") from None
    raise last_error or ProviderError(provider, "unknown", "provider request failed")
