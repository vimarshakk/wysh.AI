"""Redacted audit events; request content and secrets are intentionally absent."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import secrets
import threading
from typing import Literal


_AUDIT_PSEUDONYM_KEY = secrets.token_bytes(32)


def _pseudonymize(value: str, kind: str) -> str:
    digest = hmac.new(_AUDIT_PSEUDONYM_KEY, f"{kind}:{value}".encode("utf-8"), "sha256").hexdigest()
    return f"audit-{digest[:24]}"


@dataclass(frozen=True)
class AuditEvent:
    event_type: Literal["decision.requested", "decision.completed", "decision.abstained", "snapshot.created", "knowledge.grounded", "knowledge.abstained", "imaging.abstained", "disease.monitored", "disease.assessed", "disease.rules_evaluated", "trion.requested", "trion.completed", "trion.failed", "clinical_review.created", "clinical_review.approved", "clinical_review.rejected", "clinical_review.revision_requested", "clinical_review.conflict", "clinical_rule.created", "clinical_rule.submitted", "clinical_rule.approved", "clinical_rule.activated", "clinical_rule.expired", "clinical_rule.revoked", "clinical_rule.rejected", "clinical_rule.conflict", "clinical_workflow.requested", "clinical_workflow.completed", "clinical_workflow.abstained"]
    event_id: str
    correlation_id: str
    tenant_id: str
    subject: str
    status: str
    model_id: str | None = None
    policy_version: str | None = None
    input_hash: str | None = None
    occurred_at: str = ""
    previous_event_hash: str | None = None
    event_hash: str = ""

    def redacted_dict(self) -> dict[str, object]:
        return asdict(self)


class InMemoryAuditSink:
    """Local/test sink. Production should provide an append-only protected sink."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = threading.Lock()

    @property
    def events(self) -> tuple[AuditEvent, ...]:
        """Snapshot view; callers cannot mutate the append-only collection."""
        with self._lock:
            return tuple(self._events)

    def append(self, event: AuditEvent) -> None:
        with self._lock:
            previous_hash = self._events[-1].event_hash if self._events else None
            chained = event.__class__(**{**asdict(event), "previous_event_hash": previous_hash, "event_hash": ""})
            canonical = asdict(chained)
            canonical["event_hash"] = ""
            event_hash = sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            self._events.append(chained.__class__(**{**asdict(chained), "event_hash": event_hash}))

    def chain_is_valid(self) -> bool:
        """Verify local audit ordering and tamper evidence."""
        with self._lock:
            previous_hash = None
            for event in self._events:
                if event.previous_event_hash != previous_hash:
                    return False
                canonical = asdict(event)
                actual_hash = canonical.pop("event_hash")
                canonical["event_hash"] = ""
                expected_hash = sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
                if actual_hash != expected_hash:
                    return False
                previous_hash = event.event_hash
            return True


def new_event(event_type, correlation_id: str, tenant_id: str, subject: str, status: str, **kwargs) -> AuditEvent:
    from uuid import uuid4

    return AuditEvent(event_type, str(uuid4()), correlation_id, _pseudonymize(tenant_id, "tenant"), _pseudonymize(subject, "subject"), status, occurred_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), **kwargs)
