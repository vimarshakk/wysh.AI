"""Safe executable boundary for the synthetic WyshCare integration contract."""

from __future__ import annotations

import hashlib
import json

from .bridge_contracts import WyshAIBridgeResult, WyshCareAIBridgeRequest


def execute_synthetic_bridge(request: WyshCareAIBridgeRequest) -> WyshAIBridgeResult:
    """Validate and record a bridge request without manufacturing a conclusion."""
    canonical = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    provenance_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return WyshAIBridgeResult(
        request_id=request.request_id,
        correlation_id=request.correlation_id,
        status="ABSTAINED",
        reason="bridge contract validated; no clinical conclusion generated",
        model_id=request.requested_model.model_id,
        model_version=request.requested_model.model_version,
        evidence_refs=[item.evidence_id for item in request.evidence],
        provenance_hash=provenance_hash,
        review_required=True,
        clinical_use_authorized=False,
    )
