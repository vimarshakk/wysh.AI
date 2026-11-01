# R7A — Real CQL Runtime Integration Acceptance

Status: **ENGINEERING PASS** · **CLINICAL GOVERNANCE HOLD** · **CLINICAL VALIDATION NO-GO** · **PRODUCTION NO-GO**.

Integrated dependencies, isolated under `apps/cql-runtime`:

- `cql-execution@3.3.2` — Apache-2.0, JSON ELM execution.
- `cql-exec-fhir@2.2.0` — Apache-2.0, FHIR R4 Bundle patient source.

The runtime executes the synthetic `wysh.diabetes.rules / HasGlucoseObservation` artifact and returns patient-scoped results. FastAPI exposes this only through `/v1/reuse-accelerator/fhir-cql/upstream-runtime`, which requires development mode, synthetic tenant/patient identifiers, the exact allowlisted library/expression, and a local installed runtime. Runtime failure does not fall back silently.

Evidence:

- `apps/cql-runtime/npm test` — PASS.
- `apps/api/.venv/bin/pytest -q` — PASS.
- `artifacts/r6-test-evidence/r6c-standards-gate.json` — native boundary PASS.
- `apps/api/tests/test_reuse_accelerator.py` — upstream runtime bridge PASS.

Limitations:

- This is one allowlisted synthetic artifact, not full CQL conformance.
- Terminology service integration is not enabled.
- No clinical rule is activated or clinically approved.
- No PHI, production endpoint, or external FHIR server is used.
