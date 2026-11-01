"""Synthetic rule-governance persistence for the R6B engineering lane.

This store is deliberately separate from patient assessment review. It records
the lifecycle of a rule version and its evidence binding, never a patient's
clinical decision. The local SQLite implementation is suitable for tests and
isolated engineering only; production needs an append-only, access-controlled
store approved by clinical governance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from pathlib import Path
from typing import Literal
from uuid import uuid4


RuleStatus = Literal["DRAFT", "REVIEWED", "APPROVED", "ACTIVE", "EXPIRED", "REVOKED", "REJECTED"]
RuleAction = Literal["created", "submitted", "approved", "activated", "expired", "revoked", "rejected"]


class RuleNotFound(ValueError):
    pass


class RuleConflict(ValueError):
    pass


class RuleValidationError(ValueError):
    pass


@dataclass(frozen=True)
class RuleEvent:
    event_id: str
    rule_id: str
    version: int
    action: RuleAction
    actor_subject: str
    actor_role: str
    evidence_id: str
    note: str | None
    occurred_at: str


@dataclass(frozen=True)
class GovernedRule:
    rule_id: str
    tenant_id: str
    rule_version: str
    disease_id: str
    evidence_id: str
    intended_use: str
    status: RuleStatus
    version: int
    revision_hash: str
    created_at: str
    updated_at: str
    expires_at: str
    created_by: str
    approved_by: str | None
    approved_at: str | None
    events: tuple[RuleEvent, ...]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise RuleValidationError("timestamps must be ISO-8601") from None
    if parsed.tzinfo is None:
        raise RuleValidationError("timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


class RuleGovernanceStore:
    def __init__(self, database: str = "artifacts/r6-test-evidence/rule-governance.sqlite3") -> None:
        if database != ":memory:":
            Path(database).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(database, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.execute("PRAGMA journal_mode = WAL")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS rules (
                rule_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                rule_version TEXT NOT NULL,
                disease_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                intended_use TEXT NOT NULL,
                status TEXT NOT NULL,
                version INTEGER NOT NULL,
                revision_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                approved_by TEXT,
                approved_at TEXT,
                PRIMARY KEY (tenant_id, rule_id),
                UNIQUE (tenant_id, rule_id, version)
            );
            CREATE TABLE IF NOT EXISTS rule_events (
                event_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                action TEXT NOT NULL,
                actor_subject TEXT NOT NULL,
                actor_role TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                note TEXT,
                occurred_at TEXT NOT NULL,
                FOREIGN KEY (tenant_id, rule_id) REFERENCES rules(tenant_id, rule_id),
                UNIQUE (tenant_id, rule_id, version)
            );
            """
        )
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    def _row(self, tenant_id: str, rule_id: str) -> sqlite3.Row:
        row = self._db.execute("SELECT * FROM rules WHERE tenant_id = ? AND rule_id = ?", (tenant_id, rule_id)).fetchone()
        if row is None:
            raise RuleNotFound("clinical rule not found")
        if row["status"] not in {"EXPIRED", "REVOKED", "REJECTED"} and _parse(row["expires_at"]) <= datetime.now(timezone.utc):
            self._transition(row, "EXPIRED", "system", "clinical-governance", row["evidence_id"], None)
            row = self._db.execute("SELECT * FROM rules WHERE tenant_id = ? AND rule_id = ?", (tenant_id, rule_id)).fetchone()
        return row

    def _transition(self, row: sqlite3.Row, status: RuleStatus, actor_subject: str, actor_role: str, evidence_id: str, note: str | None, expected_version: int | None = None, action: RuleAction | None = None) -> None:
        if expected_version is not None and row["version"] != expected_version:
            raise RuleConflict("stale rule version")
        if row["evidence_id"] != evidence_id:
            raise RuleValidationError("evidence binding mismatch")
        new_version = row["version"] + 1
        now = _now()
        action_name: RuleAction = action or status.lower()  # type: ignore[assignment]
        updated = self._db.execute(
            "UPDATE rules SET status = ?, version = ?, updated_at = ?, approved_by = COALESCE(?, approved_by), approved_at = COALESCE(?, approved_at) WHERE tenant_id = ? AND rule_id = ? AND version = ?",
            (status, new_version, now, actor_subject if status == "APPROVED" else None, now if status == "APPROVED" else None, row["tenant_id"], row["rule_id"], row["version"]),
        ).rowcount
        if updated != 1:
            raise RuleConflict("concurrent rule transition")
        self._db.execute(
            "INSERT INTO rule_events(event_id, tenant_id, rule_id, version, action, actor_subject, actor_role, evidence_id, note, occurred_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid4()), row["tenant_id"], row["rule_id"], new_version, action_name, actor_subject, actor_role, evidence_id, note, now),
        )
        self._db.commit()

    def create(self, *, tenant_id: str, rule_id: str, rule_version: str, disease_id: str, evidence_id: str, intended_use: str, revision_hash: str, expires_at: str, actor_subject: str) -> GovernedRule:
        if not tenant_id.startswith("synthetic-"):
            raise RuleValidationError("only synthetic governance tenants are allowed")
        expiry = _parse(expires_at)
        if expiry <= datetime.now(timezone.utc):
            raise RuleValidationError("rule expiry must be in the future")
        now = _now()
        try:
            self._db.execute("INSERT INTO rules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (rule_id, tenant_id, rule_version, disease_id, evidence_id, intended_use, "DRAFT", 1, revision_hash, now, now, expiry.isoformat().replace("+00:00", "Z"), actor_subject, None, None))
            self._db.execute("INSERT INTO rule_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (str(uuid4()), tenant_id, rule_id, 1, "created", actor_subject, "rule-engineer", evidence_id, None, now))
            self._db.commit()
        except sqlite3.IntegrityError:
            self._db.rollback()
            raise RuleConflict("rule version already exists") from None
        return self.get(tenant_id, rule_id)

    def get(self, tenant_id: str, rule_id: str) -> GovernedRule:
        row = self._row(tenant_id, rule_id)
        event_rows = self._db.execute("SELECT * FROM rule_events WHERE tenant_id = ? AND rule_id = ? ORDER BY version", (tenant_id, rule_id)).fetchall()
        return GovernedRule(
            rule_id=row["rule_id"], tenant_id=row["tenant_id"], rule_version=row["rule_version"], disease_id=row["disease_id"], evidence_id=row["evidence_id"], intended_use=row["intended_use"], status=row["status"], version=row["version"], revision_hash=row["revision_hash"], created_at=row["created_at"], updated_at=row["updated_at"], expires_at=row["expires_at"], created_by=row["created_by"], approved_by=row["approved_by"], approved_at=row["approved_at"], events=tuple(RuleEvent(event_id=item["event_id"], rule_id=item["rule_id"], version=item["version"], action=item["action"], actor_subject=item["actor_subject"], actor_role=item["actor_role"], evidence_id=item["evidence_id"], note=item["note"], occurred_at=item["occurred_at"]) for item in event_rows),
        )

    def transition(self, *, tenant_id: str, rule_id: str, expected_version: int, action: RuleAction, evidence_id: str, actor_subject: str, actor_role: str, note: str | None = None) -> GovernedRule:
        row = self._row(tenant_id, rule_id)
        allowed: dict[str, set[str]] = {"submitted": {"DRAFT"}, "approved": {"REVIEWED"}, "activated": {"APPROVED"}, "revoked": {"APPROVED", "ACTIVE"}, "rejected": {"REVIEWED"}}
        target: dict[str, RuleStatus] = {"submitted": "REVIEWED", "approved": "APPROVED", "activated": "ACTIVE", "revoked": "REVOKED", "rejected": "REJECTED"}
        if action not in allowed or row["status"] not in allowed[action]:
            raise RuleConflict("invalid rule lifecycle transition")
        if action == "approved" and _parse(row["expires_at"]) <= datetime.now(timezone.utc):
            raise RuleValidationError("expired rule cannot be approved")
        self._transition(row, target[action], actor_subject, actor_role, evidence_id, note, expected_version, action)
        return self.get(tenant_id, rule_id)
