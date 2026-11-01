# R7D Real Local MedGemma and Model Safety

R7D uses the existing `MedGemmaProvider` through the R7C orchestration route:

`POST /v1/clinical-intelligence/synthetic-workflow`

The provider is local Ollama-compatible inference only. The route requires the configured model to be enabled in both the manifest and `MODEL_ENABLED_IDS`, validates the response against the `ClinicalExplanation` schema, and records provider/model/latency/schema-validation telemetry. `MEDGEMMA_MODEL_VERSION` is carried into workflow provenance when supplied.

The deterministic safety gate blocks:

- fabricated evidence references;
- diagnostic, treatment, emergency, medication, or dose instructions;
- prompt-injection and instruction-override language;
- explanations without limitations;
- conflicting values for the same metric at the same timestamp.

Deterministic calculations and CQL results remain separate structured fields. Model text cannot replace, authorize, or mutate them. Any model or safety failure produces an abstention or `MODEL_UNAVAILABLE` result; no deterministic fixture is used by the live gate.

Run the live gate from `apps/api`:

```sh
MEDGEMMA_MODEL=medgemma:latest ./.venv/bin/python scripts/run_r7d_live_medgemma_gate.py
```

The gate uses a bounded 60-second local provider timeout and zero retries so cold-start latency does not multiply model load. It writes sanitized evidence to `artifacts/r7-test-evidence/r7d-live-medgemma-gate.json`. If the local runtime or requested model is absent, it records `BLOCKED` and exits with status 2. That is an honest connectivity result, not a passing substitute.

R7D remains synthetic isolated engineering. Gemini and TRION remain disabled unless independently configured and verified. Clinical governance is HOLD, clinical validation is NO-GO, and production deployment is NO-GO.
