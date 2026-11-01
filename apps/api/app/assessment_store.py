"""Persistent synthetic clinician-assessment records, distinct from model approval."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class AssessmentConflict(Exception):
    pass


@dataclass(frozen=True)
class AssessmentRecord:
    assessment_id: str
    tenant_id: str
    patient_id: str
    evidence_hash: str
    review_id: str
    state: str
    version: int
    created_at: str
    approved_by: str | None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AssessmentStore:
    def __init__(self, path: str | Path | None = None) -> None:
        default = Path(__file__).resolve().parents[3] / "artifacts" / "r10-test-evidence" / "assessment.sqlite3"
        self.path = ":memory:" if path == ":memory:" else str(path or default)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS assessments (
            assessment_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, patient_id TEXT NOT NULL,
            evidence_hash TEXT NOT NULL, review_id TEXT NOT NULL UNIQUE, state TEXT NOT NULL,
            version INTEGER NOT NULL, created_at TEXT NOT NULL, approved_by TEXT
        );
        CREATE TABLE IF NOT EXISTS assessment_events (
            event_id TEXT PRIMARY KEY, assessment_id TEXT NOT NULL, version INTEGER NOT NULL,
            action TEXT NOT NULL, actor TEXT NOT NULL, occurred_at TEXT NOT NULL,
            UNIQUE(assessment_id, version)
        );
        """)
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def create_draft(self, *, tenant_id: str, patient_id: str, evidence_hash: str, review_id: str) -> AssessmentRecord:
        assessment_id, now = f"assessment-{uuid4()}", _now()
        with self.db:
            self.db.execute("INSERT INTO assessments VALUES (?, ?, ?, ?, ?, 'DRAFT', 1, ?, NULL)", (assessment_id, tenant_id, patient_id, evidence_hash, review_id, now))
            self.db.execute("INSERT INTO assessment_events VALUES (?, ?, 1, 'created', ?, ?)", (str(uuid4()), assessment_id, "system:r10", now))
        return self.get(assessment_id, tenant_id=tenant_id, patient_id=patient_id)

    def approve_from_review(self, *, assessment_id: str, tenant_id: str, patient_id: str, review_id: str, review_state: str, actor: str, expected_version: int) -> AssessmentRecord:
        if review_state != "APPROVED" or not actor:
            raise AssessmentConflict("only an approved persisted clinician review can finalize an assessment")
        row = self.db.execute("SELECT * FROM assessments WHERE assessment_id = ? AND tenant_id = ? AND patient_id = ?", (assessment_id, tenant_id, patient_id)).fetchone()
        if row is None or row["review_id"] != review_id or row["version"] != expected_version or row["state"] != "DRAFT":
            raise AssessmentConflict("assessment identity or version conflict")
        now = _now()
        with self.db:
            updated = self.db.execute("UPDATE assessments SET state = 'APPROVED', version = ?, approved_by = ? WHERE assessment_id = ? AND version = 1", (expected_version + 1, actor, assessment_id))
            if updated.rowcount != 1:
                raise AssessmentConflict("assessment concurrency conflict")
            self.db.execute("INSERT INTO assessment_events VALUES (?, ?, ?, 'approved_from_clinician_review', ?, ?)", (str(uuid4()), assessment_id, expected_version + 1, actor, now))
        return self.get(assessment_id, tenant_id=tenant_id, patient_id=patient_id)

    def get(self, assessment_id: str, *, tenant_id: str, patient_id: str) -> AssessmentRecord:
        row = self.db.execute("SELECT * FROM assessments WHERE assessment_id = ? AND tenant_id = ? AND patient_id = ?", (assessment_id, tenant_id, patient_id)).fetchone()
        if row is None:
            raise AssessmentConflict("assessment not found")
        return AssessmentRecord(**dict(row))
