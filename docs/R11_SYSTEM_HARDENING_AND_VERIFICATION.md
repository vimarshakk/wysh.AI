# wysh.AI R11 — System Hardening and Independent Verification

R11 is an isolated engineering verification milestone. It does not establish clinical validity, regulatory clearance, or production readiness.

The local audit sink emits a SHA-256 hash chain over redacted events and the
synthetic suite verifies its continuity and tamper detection. This is
tamper-evident engineering evidence, not a substitute for a protected
append-only production audit store.

## R11A security and authorization

The hardening suite covers cross-tenant and patient-scope denial, purpose-of-use and consent matching, delegated-access mismatch, stale review versions, terminal-review replay, assessment replay, immutable audit snapshots, and stable concurrent authorization checks.

## R11B adversarial safety

`run_r11_live_safety_gate.py` sends prompt-injection, medication/dose, and fabricated-evidence prompts to the actual local MedGemma provider when the configured runtime is ready. It never substitutes a fixture. If Ollama or `medgemma:latest` is unavailable, the artifact is `BLOCKED` and R11 remains `PARTIAL_BLOCKED`.

## R11C performance and reliability

The aggregate gate records local authorization latency, configured provider timeout and retry limits, and whether live model latency is available. The reported authorization benchmark is an engineering measurement, not an SLO. Model latency is not reported when the runtime is unavailable.

## R11D interoperability

`interoperability_contracts.py` provides a synthetic FHIR/ABDM-compatible consent and exchange contract. It validates synthetic patient scope, granted consent, declared health-information types, and the synthetic FHIR marker. No live ABDM or WyshCare service is contacted.

## R11E evidence and release governance

Run:

```bash
PYTHONPATH=. ./.venv/bin/python scripts/run_r11_live_safety_gate.py
PYTHONPATH=. ./.venv/bin/python scripts/run_r11_gate.py
```

Evidence is written to `artifacts/r11-test-evidence/`. The aggregate status is `PASS` only when live MedGemma adversarial evaluation passes; otherwise it is explicitly `PARTIAL_BLOCKED`.

Clinical governance remains `HOLD`, clinical validation is `NO-GO`, production is `NO-GO`, and WyshCare remains unchanged.
