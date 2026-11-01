# Test and Acceptance Plan

Required gates:

- Unit: ELM identity, FHIR resource mapping, unsupported code, missing value, invalid timestamps.
- Contract: FastAPI request/response schemas and synthetic-only enforcement.
- Security: cross-tenant, forged role, missing scope, replayed approval, evidence substitution.
- Clinical safety: no diagnosis/treatment output, missing/stale/conflicting evidence abstention.
- Regression: full backend suite, R4/R5/R6A/R6B gates.
- Console: typecheck and production build.

The current standards gate is `apps/api/tests/test_reuse_accelerator.py` plus the dedicated R6C script. Full CQL conformance is explicitly not claimed until a pinned upstream runtime is independently tested.
