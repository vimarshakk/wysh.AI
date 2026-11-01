# R4A — Clinical review integrity

Status: **ENGINEERING PASS / CLINICAL VALIDATION NO-GO**

R4A adds a local, synthetic-only review boundary to the FastAPI service. A
review cannot be created or changed without a signed bearer token containing
the required scope and the `clinician` role. Tenant and patient identifiers are
checked against the token before every write or read.

## Contract

- `POST /v1/clinical-reviews` creates a version-1 `DRAFT` review.
- `GET /v1/clinical-reviews/{review_id}?tenant_id=...&patient_id=...` retrieves the review and its event history.
- `POST /v1/clinical-reviews/{review_id}/decision` accepts `approve`, `reject`, or `request_revision` with an `expected_version`.
- SQLite stores the review aggregate and append-only events under `artifacts/r4-test-evidence/clinical-review.sqlite3` for local validation.
- A compare-and-swap version check returns `409` for stale or terminal decisions.

## Evidence

- Backend: `68 passed` with `apps/api/tests/test_clinical_review.py` and the existing suite.
- Console: TypeScript check and Next.js production build pass.
- Negative cases: missing bearer, missing clinician role, wrong patient scope, stale version, and terminal-state mutation are covered.
- Audit sink emits redacted `clinical_review.*` events with the correlation ID and policy version.

The local SQLite store and in-memory audit sink are engineering implementations;
they are not approved for PHI or production deployment. Production remains
blocked pending managed persistence, durable append-only audit, key management,
clinical validation, and WyshCare authorization integration.
