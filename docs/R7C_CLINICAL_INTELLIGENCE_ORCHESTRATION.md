# R7C Clinical Intelligence Orchestration

R7C adds one bounded synthetic workflow at:

`POST /v1/clinical-intelligence/synthetic-workflow`

The workflow composes existing wysh.AI contracts in this order:

`FHIR R4 → terminology validation → deterministic calculations → native JSON ELM → pinned upstream CQL runtime → typed MedGemma explanation → deterministic safety evaluation → clinician review`

The response exposes a status, latency, reason, and provenance references for every stage. Raw FHIR and model prompts are not returned or persisted. The response is always marked `synthetic_only: true`, `clinical_use_authorized: false`, `review_required: true`, and `review_state: DRAFT_ONLY`.

The endpoint uses the configured local model gateway. If inference is disabled, the model is unavailable, the typed output is invalid, evidence references are unknown, or unsafe clinical language is returned, the workflow abstains. There is no cloud or mock fallback in the production path.

The existing `/v1/clinical-reviews` endpoints remain a separate authenticated boundary. The R7C gate creates a draft review and approves it using a synthetic clinician token, proving persistence and concurrency-safe review semantics without treating model output as authorization.

Run the reproducible gate from `apps/api`:

```sh
./.venv/bin/python scripts/run_r7c_workflow_gate.py
```

The gate writes sanitized evidence to `artifacts/r7-test-evidence/r7c-workflow-gate.json`. Its model stage is a typed synthetic contract stub so the gate is deterministic; real local MedGemma availability must still be checked through `/v1/providers/medgemma/ready` and does not imply clinical approval.

R7C remains isolated engineering only. Clinical governance is HOLD, clinical validation is NO-GO, and production deployment is NO-GO.
