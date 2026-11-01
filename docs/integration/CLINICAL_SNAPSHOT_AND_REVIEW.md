# Clinical Snapshot and Clinician Review — R2 preparation

The R2 contract is a synthetic-only handoff from typed clinical facts to a human review surface. It does not authorize live patient data, clinical inference, treatment recommendations, or direct writes to a source-of-truth system.

## Snapshot

`packages/contracts/clinical-snapshot-v1.schema.json` defines a bounded snapshot request: synthetic tenant/patient identifiers, up to 100 facts, and at least one typed evidence item per fact. The runtime implementation is `apps/api/app/schemas.py` and `/v1/snapshots` remains disabled outside development.

The UI should render each fact with its evidence source and recorded time. It must not render an ungrounded model claim as a fact and must preserve the snapshot ID and correlation ID for review support.

## Review lifecycle

The initial state is `DRAFT`. A reviewer may submit the versioned action in `clinician-review-action-v1.schema.json` to transition `DRAFT` to `APPROVED` or `REJECTED`. Every action requires a reviewer subject, role, reason, correlation ID, and optional evidence references.

Approval means “reviewed for this workflow,” not “clinically authorized.” The runtime response continues to set `human_review_required=true` and `clinical_use_authorized=false`. A future production implementation must add authorization, immutable audit storage, conflict handling, and source-system write controls before this contract can be used with live data.

## UI safety requirements

- Show synthetic/environment status prominently.
- Show evidence references beside every generated or summarized fact.
- Keep approve/reject actions disabled until the snapshot is complete and evidence is available.
- Require a reason for both approval and rejection.
- Never expose provider credentials, raw prompts, hidden chain-of-thought, or uncalibrated confidence.
- Treat an abstention as a normal review state, not an error to override automatically.
