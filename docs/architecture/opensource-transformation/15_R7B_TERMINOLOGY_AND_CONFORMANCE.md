# R7B — Terminology and CQL Conformance Acceptance

Status: **ENGINEERING PASS** · **CLINICAL GOVERNANCE HOLD** · **CLINICAL VALIDATION NO-GO** · **PRODUCTION NO-GO**.

Implemented:

- Exact runtime/version and lockfile integrity gate for `cql-execution@3.3.2` and `cql-exec-fhir@2.2.0`.
- Child-process isolation with an eight-second wall-clock timeout, ten-second CPU limit on POSIX hosts, Node V8 768 MiB old-space limit, 200 KiB request limit, 75 KiB ELM limit, and 100 Bundle-entry limit.
- Synthetic FHIR R4 missing-patient/missing-observation and oversized-request tests.
- Versioned synthetic terminology-provider contract for CodeSystem-like code validation and a synthetic diabetes ValueSet URL.
- Unknown codes, display mismatches, unsupported ValueSets, and non-synthetic requests fail closed.
- Differential runtime tests for a positive Observation retrieve and an empty Observation collection.

Snowstorm remains `PLANNED`, not integrated. No SNOMED CT distribution or licensed terminology content was downloaded. The local terminology contract is not a clinical terminology service.

Evidence:

- `apps/api/scripts/run_r7b_integrity_gate.py`
- `artifacts/r7-test-evidence/r7b-runtime-integrity.json`
- `apps/cql-runtime/test/runtime.test.mjs`
- `apps/api/tests/test_reuse_accelerator.py`

The upstream runtime remains an execution component, not a clinical approval engine. General CQL conformance requires a broader pinned test suite and is not implied by this single vertical slice.
