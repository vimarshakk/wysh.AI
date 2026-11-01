from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from uuid import uuid4

from .config import Settings


MAX_TRION_REQUEST_BYTES = 64 * 1024
MAX_TRION_RESPONSE_BYTES = 1024 * 1024


@dataclass(frozen=True)
class TrionResult:
    status: str
    correlation_id: str
    idempotency_key: str
    payload: dict


class TrionError(RuntimeError):
    pass


class TrionClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def execute(self, request_payload: dict, *, correlation_id: str | None = None, idempotency_key: str | None = None) -> TrionResult:
        correlation_id = correlation_id or str(uuid4())
        idempotency_key = idempotency_key or str(uuid4())
        if not self.settings.trion_enabled:
            raise TrionError("TRION integration is disabled")
        if not self.settings.trion_base_url or not self.settings.trion_api_key:
            raise TrionError("TRION endpoint or credentials are not configured")
        if self.settings.configuration_errors():
            raise TrionError("TRION configuration is invalid")
        url = f"{self.settings.trion_base_url.rstrip('/')}/{self.settings.trion_path.lstrip('/')}"
        encoded_payload = json.dumps(request_payload).encode("utf-8")
        if len(encoded_payload) > MAX_TRION_REQUEST_BYTES:
            raise TrionError("TRION request exceeds the bounded payload limit")
        request = urllib.request.Request(
            url,
            data=encoded_payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.trion_api_key}",
                "X-Correlation-Id": correlation_id,
                "Idempotency-Key": idempotency_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.settings.trion_timeout_ms / 1000) as response:
                raw_body = response.read(MAX_TRION_RESPONSE_BYTES + 1)
                if len(raw_body) > MAX_TRION_RESPONSE_BYTES:
                    raise TrionError("TRION response exceeds the bounded payload limit")
                body = json.loads(raw_body.decode("utf-8"))
                if response.status < 200 or response.status >= 300:
                    raise TrionError(f"TRION returned HTTP {response.status}")
                if body.get("schemaVersion") != 1 or body.get("generatedBy") != "TRION":
                    raise TrionError("TRION response failed schemaVersion/generatedBy validation")
                return TrionResult("success", correlation_id, idempotency_key, body)
        except urllib.error.HTTPError as exc:
            raise TrionError(f"TRION returned HTTP {exc.code}") from None
        except (TimeoutError, urllib.error.URLError):
            raise TrionError("TRION request timed out or endpoint was unavailable") from None
        except json.JSONDecodeError:
            raise TrionError("TRION returned invalid JSON") from None
