# Cross-cutting synthetic E2E contract

`apps/api/scripts/run_worldclass_synthetic_e2e.py` is the current integration
harness for the safety boundary. It exercises the FastAPI application in
memory using synthetic fixtures and records only boolean check results.

The harness verifies:

- synthetic patient workspace availability;
- missing-evidence abstention and empty route telemetry;
- typed WyshCare bridge abstention;
- TRION disabled-by-default behavior;
- authenticated persistent clinician review;
- unsafe model-output abstention;
- production inference rejection;
- redacted metrics.

It deliberately reports `model_execution: NOT_RUN_CONTRACT_HARNESS`. It is not
a substitute for the real local MedGemma gate, and it never promotes a fixture
to model evidence. The sanitized artifact is
`artifacts/integration/worldclass-synthetic-e2e.json`.
