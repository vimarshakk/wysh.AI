# wysh.AI R10A–R10E — Clinical Workflow Integration

R10A–R10E is isolated, synthetic-only engineering. It does not establish clinical validity, production authorization, or autonomous clinical capability.

## R10A unified workbench

`POST /v1/clinical-workbench/synthetic` accepts a typed clinical workflow response and a typed multimodal evidence envelope. It returns independent clinical and imaging statuses, imaging findings only when a safe draft exists, provenance, review-required state, and explicit clinical-use denial.

The existing Clinical Console remains an independent local surface. The backend workbench contract is the integration boundary for a future console view; no direct database connection or WyshCare modification is introduced.

## R10B patient-context authorization

Workbench access requires all of:

- matching tenant and patient scope;
- a clinician or clinical-reviewer role;
- `clinical-workbench:read` scope;
- `purpose_of_use=synthetic-evaluation`;
- matching synthetic consent identity;
- matching delegation identity when delegated access is asserted.

Scope, purpose, consent, and delegation failures fail closed.

## R10C assessment lifecycle

`AssessmentStore` persists a `DRAFT` assessment record and permits `APPROVED` only when a persisted clinician review is already `APPROVED`, the review identity and evidence hash match, and the expected version is current. Assessment records and model/rule governance remain separate.

## R10D safety boundary

The workbench is draft-only and cannot prescribe, diagnose, trigger emergency action, or authorize clinical use. Imaging `ABSTAINED` remains unavailable evidence and is never interpreted as a negative finding.

## R10E synthetic integration gate

Run:

```bash
PYTHONPATH=. ./.venv/bin/python scripts/run_r10_gate.py
```

Evidence is written to `artifacts/r10-test-evidence/r10-gate.json`. Clinical governance remains `HOLD`, clinical validation is `NO-GO`, and production is `NO-GO`.
