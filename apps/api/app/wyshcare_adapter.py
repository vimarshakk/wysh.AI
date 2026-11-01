"""Synthetic WyshCare-side client for the versioned wysh.AI bridge.

The adapter accepts only the typed bridge request and a caller-supplied
transport.  Keeping transport injection explicit makes the emulator useful
without introducing a production network client or silently enabling an
external endpoint.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from .bridge_contracts import WyshAIBridgeResult, WyshCareAIBridgeRequest


class BridgeResponse(Protocol):
    status_code: int

    def json(self) -> Any: ...


class BridgeTransport(Protocol):

    def __call__(self, *, headers: Mapping[str, str], json: Mapping[str, Any]) -> BridgeResponse: ...


class WyshCareBridgeError(RuntimeError):
    """Raised when the bridge response cannot be safely consumed."""


class WyshCareBridgeClient:
    """Consume the synthetic wysh.AI bridge as a WyshCare adapter would."""

    def __init__(self, transport: BridgeTransport) -> None:
        self._transport = transport

    def request_clinical_draft(
        self,
        request: WyshCareAIBridgeRequest,
        *,
        idempotency_key: str | None = None,
    ) -> WyshAIBridgeResult:
        if request.synthetic is not True:
            raise WyshCareBridgeError("the adapter accepts synthetic requests only")
        if request.review_required is not True or request.clinical_use_authorized is not False:
            raise WyshCareBridgeError("bridge requests must remain review-required and non-authorizing")

        replay_key = idempotency_key or request.request_id
        if not replay_key or len(replay_key) > 256:
            raise WyshCareBridgeError("a bounded idempotency key is required")

        response = self._transport(
            headers={"Idempotency-Key": replay_key, "X-Correlation-Id": request.correlation_id},
            json=request.model_dump(mode="json"),
        )
        if response.status_code != 200:
            raise WyshCareBridgeError(f"bridge request failed with status {response.status_code}")

        try:
            result = WyshAIBridgeResult.model_validate(response.json())
        except Exception as exc:  # Pydantic's detailed error is not safe to expose upstream.
            raise WyshCareBridgeError("bridge response failed typed validation") from exc

        if result.request_id != request.request_id or result.correlation_id != request.correlation_id:
            raise WyshCareBridgeError("bridge response identity does not match the request")
        if result.review_required is not True or result.clinical_use_authorized is not False:
            raise WyshCareBridgeError("bridge response crossed the clinical authorization boundary")
        return result
