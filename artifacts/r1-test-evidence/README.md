# R1 test evidence

Evidence files in this directory must be synthetic-only and sanitized. The real-provider smoke command writes model ID, status, latency, schema-validation result, and sanitized error classifications only. It must never write API keys, raw prompts, raw provider responses, PHI, or database credentials.

`local-provider-http-e2e.json` is transport-contract evidence from a synthetic
loopback server. Its `PASS_LOCAL_EMULATOR` entries do not prove that Gemini,
MedGemma, OpenAI-compatible, or TRION production endpoints are available.

`promotion-gate.json` contains only model IDs and registry validation results;
it never contains provider credentials or model responses.

`verification-summary.json` contains only check names, exit codes, aggregate
status, and sanitized blocked/failed integration IDs. A
`PASS_WITH_BLOCKED_REAL_INTEGRATIONS` result means all local gates passed but
some real provider infrastructure is unavailable; it is not an R1 completion
claim. The release runner intentionally discards subprocess output.

`medgemma-decision-e2e.json` proves only the synthetic service path and safety
invariants. It does not establish clinical accuracy, calibration, or approval.

`medgemma-contract-evaluation.json` is a two-case real local model contract
check. It tests output shape and safety invariants only; it is not a clinical
benchmark or efficacy claim.

R2 preparation evidence is kept separately in `artifacts/r2-test-evidence/`.
`provenance-gate.json` is synthetic-only and checks hash determinism, evidence
binding, response provenance, and audit redaction. It does not authorize live
clinical use or external provider connectivity.
