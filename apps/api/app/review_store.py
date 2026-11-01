"""Local persistent clinical-review store for synthetic engineering validation.

The store records a review aggregate and append-only decision events. It is
deliberately SQLite-backed for local validation; production use requires a
managed transactional store and an append-only audit sink approved for PHI.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4


ReviewState = Literal["DRAFT", "APPROVED", "REJECTED", "REVISION_REQUESTED"]
ReviewAction = Literal["approve", "reject", "request_revision"]


class ReviewNotFound(Exception):
    pass


class ReviewConflict(Exception):
    pass


@dataclass(frozen=True)
class ReviewEvent:
    event_id: str
    review_id: str
    version: int
    action: str
    actor_subject: str
    actor_role: str
    note: str | None
    occurred_at: str


@dataclass(frozen=True)
class ClinicalReview:
    review_id: str
    tenant_id: str
    patient_id: str
    disease_id: str
    assessment_id: str
    assessment_input_hash: str
    state: ReviewState
    version: int
    created_at: str
    updated_at: str
    created_by: str
    latest_action: str
    events: tuple[ReviewEvent, ...]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ReviewStore:
    def __init__(self, path: str | Path | None = None) -> None:
        default = Path(__file__).resolve().parents[3] / "artifacts" / "r4-test-evidence" / "clinical-review.sqlite3"
        self.path = ":memory:" if path == ":memory:" else str(path or default)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS reviews (
                review_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                patient_id TEXT NOT NULL,
                disease_id TEXT NOT NULL,
                assessment_id TEXT NOT NULL,
                assessment_input_hash TEXT NOT NULL,
                state TEXT NOT NULL,
                version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS review_events (
                event_id TEXT PRIMARY KEY,
                review_id TEXT NOT NULL REFERENCES reviews(review_id),
                version INTEGER NOT NULL,
                action TEXT NOT NULL,
                actor_subject TEXT NOT NULL,
                actor_role TEXT NOT NULL,
                note TEXT,
                occurred_at TEXT NOT NULL,
                UNIQUE(review_id, version)
            );
            """
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def create(self, *, tenant_id: str, patient_id: str, disease_id: str, assessment_id: str, assessment_input_hash: str, actor_subject: str) -> ClinicalReview:
        review_id, event_id, timestamp = str(uuid4()), str(uuid4()), _now()
        with self._connection:
            self._connection.execute(
                "INSERT INTO reviews VALUES (?, ?, ?, ?, ?, ?, 'DRAFT', 1, ?, ?, ?)",
                (review_id, tenant_id, patient_id, disease_id, assessment_id, assessment_input_hash, timestamp, timestamp, actor_subject),
            )
            self._connection.execute(
                "INSERT INTO review_events VALUES (?, ?, 1, 'created', ?, 'clinician', NULL, ?)",
                (event_id, review_id, actor_subject, timestamp),
            )
        return self.get(review_id, tenant_id=tenant_id, patient_id=patient_id)

    def decide(self, *, review_id: str, tenant_id: str, patient_id: str, expected_version: int, action: ReviewAction, actor_subject: str, note: str | None) -> ClinicalReview:
        row = self._connection.execute("SELECT * FROM reviews WHERE review_id = ? AND tenant_id = ? AND patient_id = ?", (review_id, tenant_id, patient_id)).fetchone()
        if row is None:
            raise ReviewNotFound
        if row["version"] != expected_version:
            raise ReviewConflict
        if row["state"] in {"APPROVED", "REJECTED"}:
            raise ReviewConflict
        state: ReviewState = {"approve": "APPROVED", "reject": "REJECTED", "request_revision": "REVISION_REQUESTED"}[action]  # type: ignore[assignment]
        timestamp, next_version = _now(), expected_version + 1
        with self._connection:
            updated = self._connection.execute(
                "UPDATE reviews SET state = ?, version = ?, updated_at = ? WHERE review_id = ? AND version = ?",
                (state, next_version, timestamp, review_id, expected_version),
            )
            if updated.rowcount != 1:
                raise ReviewConflict
            self._connection.execute(
                "INSERT INTO review_events VALUES (?, ?, ?, ?, ?, 'clinician', ?, ?)",
                (str(uuid4()), review_id, next_version, action, actor_subject, note, timestamp),
            )
        return self.get(review_id, tenant_id=tenant_id, patient_id=patient_id)

    def get(self, review_id: str, *, tenant_id: str, patient_id: str) -> ClinicalReview:
        row = self._connection.execute("SELECT * FROM reviews WHERE review_id = ? AND tenant_id = ? AND patient_id = ?", (review_id, tenant_id, patient_id)).fetchone()
        if row is None:
            raise ReviewNotFound
        events = tuple(ReviewEvent(**dict(item)) for item in self._connection.execute("SELECT event_id, review_id, version, action, actor_subject, actor_role, note, occurred_at FROM review_events WHERE review_id = ? ORDER BY version", (review_id,)).fetchall())
        return ClinicalReview(
            review_id=row["review_id"], tenant_id=row["tenant_id"], patient_id=row["patient_id"], disease_id=row["disease_id"],
            assessment_id=row["assessment_id"], assessment_input_hash=row["assessment_input_hash"], state=row["state"], version=row["version"],
            created_at=row["created_at"], updated_at=row["updated_at"], created_by=row["created_by"], latest_action=events[-1].action, events=events,
        )
