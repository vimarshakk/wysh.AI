# wysh.AI R1 integration report

Date: 2026-10-24 (Asia/Kolkata)

## Scope and safety

This report covers the standalone `wysh.AI` project and read-only inspection of `/Users/vimarshakprudhvi/wyshcare/backend`. No WyshCare source was modified. No production Supabase, Firebase, ABDM, or clinical records were accessed. No AWS ECS deployment or model download was performed.

## Compatibility findings

- WyshCare’s provider types are `gemini`, `medgemma`, `openai`, `openrouter`, `nvidia-nim`, and `ollama`.
- WyshCare’s Gemini adapter uses `GEMINI_API_KEY` and `GEMINI_MODEL`.
- WyshCare’s MedGemma adapter uses an Ollama-compatible `/api/chat` endpoint, preferring `OLLAMA_HOST`, then `OLLAMA_URL`, and `MEDGEMMA_MODEL`.
- Self-hosted OpenAI-compatible endpoints are supported through explicit `OPENAI_COMPATIBLE_*` settings for vLLM, llama.cpp servers, or equivalent gateways.
- WyshCare’s AI orchestrator uses `AI_PROVIDER`, `AI_FALLBACK_ORDER`, `AI_CACHE_ENABLED`, and `AI_CACHE_TTL_MS`; wysh.AI does not import or silently reproduce this fallback chain because its security boundary is independent.
- WyshCare contains a versioned TRION-shaped FHIR draft schema but no verified TRION network implementation in the inspected source.

See [MODEL_CONNECTIVITY_MATRIX.md](MODEL_CONNECTIVITY_MATRIX.md) and [TRION_CONTRACTS.md](TRION_CONTRACTS.md).

## Delivered

- Allowlisted, explicit env loader with `.env.example`; secrets never enter responses or telemetry.
- Strict signed gateway-token boundary with HS256 local mode and RS256/JWKS production mode, algorithm pinning, issuer/audience/expiry validation, tenant and patient scope checks, and per-route scopes.
- Correlation-ID middleware for request tracing without logging prompts, PHI, or authorization tokens.
- Gemini and MedGemma adapters with timeout, bounded retry, error classification, structured JSON parsing, Pydantic validation, and token telemetry where the provider reports it.
- Policy-aware model gateway with explicit local-first `auto` routing and cloud fallback disabled by default.
- Runtime model promotion gate requiring both manifest enablement and explicit `MODEL_ENABLED_IDS` allowlisting in addition to provider configuration.
- Standalone model-promotion gate command producing sanitized registry evidence before runtime promotion.
- One-command release-check runner aggregating all mandatory synthetic, security, adapter, and sanitized real-provider checks.
- Typed runtime model registry and read-only promotion-status endpoint.
- Packaged model-registry fallback plus source/package consistency test for deployment artifacts.
- MedGemma readiness probe; no large download when infrastructure is absent.
- Typed `/v1/decisions` API for synthetic, non-diagnostic workflow decisions with abstention, independent policy checks, evidence references, model ID, and policy version.
- Typed evidence references, deterministic input hash, generated timestamp, model/policy provenance, and redacted audit events for every decision and snapshot.
- Evidence-grounding gate that forces abstention without typed evidence and suppresses uncalibrated model confidence.
- Evidence is checked before provider invocation, so unsupported requests do not consume model calls.
- Authenticated TRION adapter with correlation IDs, idempotency keys, timeout, and versioned response validation.
- Typed `/v1/trion/fhir-draft` boundary with fail-closed disabled/unavailable behavior and redacted audit events.
- Unit/contract tests and a real-provider smoke command that records only sanitized evidence.
- Synthetic evaluation harness covering valid-option selection and required abstention.
- Synthetic local HTTP E2E harness driving Gemini, MedGemma/Ollama, OpenAI-compatible, and TRION adapters over loopback transport; explicitly separated from real-provider evidence.
- Synthetic FastAPI decision E2E through the real local MedGemma gateway, preserving model ID, evidence provenance, human-review requirement, and disabled clinical authorization.
- Multi-case real local MedGemma contract evaluation covering permitted options, schema output, provenance, confidence suppression, and human-review invariants; explicitly not a clinical-accuracy evaluation.
- Security release gate for production isolation and real tenant/patient rejection.
- Synthetic Clinical Snapshot → decision E2E with evidence provenance preservation.
- R2 preparation contracts for Clinical Snapshot, clinician review state transitions, synthetic FHIR fixtures, evaluation cases, and provenance-gate checks.
- Adversarial synthetic safety evaluation covering policy bypass and isolation attempts.
- Low-cardinality Prometheus-style runtime metrics with success, schema-validation, failure, HTTP, and TRION counters; no tenant, patient, prompt, model, or token labels.
- Shared application-profile catalog for patient companion, clinician copilot, care navigation, operations, and research lanes.
- Synthetic deterministic evidence-grounding endpoint with bounded lexical retrieval, citation-preserving hits, query hashes, and fail-closed abstention.
- Metadata-only imaging analysis contract with synthetic fixture, explicit modality/task fields, content hashing, and fail-closed abstention.
- Original structured report-draft composition from typed observations and segmentation-job handoff for point, box, scribble, and text prompts; no masks or diagnoses are fabricated.
- Open-source adoption matrix for MONAI, OHIF-AI, RadVision AI, MedRAX, and candidate segmentation/retrieval projects.
- Machine-readable open-source governance ledger and adapter-only license gate; no third-party code or model weights are vendored.
- WDI-20 catalog with 20 prioritized conditions, six Phase 1 workflow definitions, descriptive longitudinal monitoring, evidence-preserving trend summaries, and synthetic E2E validation.
- Original deterministic disease-rule interface for measurement completeness and synthetic FHIR Observation mapping; no external CQL runtime or disease-management application is vendored.
- Phase 1 shared clinical-intelligence engine with versioned diabetes, hypertension, and CKD packs; unit normalization, temporal quality checks, missing-data review findings, provenance hashes, abstention, and draft-only clinician care-plan outputs.
- Reproducible synthetic Phase 1 evaluation with 20 scenarios per disease (60 total), including missing, stale, paired-BP, unit-conversion, medication-review, and provenance cases.

## Evidence status

| Area | Result | Evidence |
|---|---|---|
| Existing API regression tests | PASS (5 tests) | `apps/api/tests/test_api.py` |
| R1/R2 contract/provider tests | PASS (52 tests) | `apps/api/tests/test_r1.py`, `apps/api/tests/test_api.py` |
| Synthetic imaging contract E2E | PASS; metadata-only and abstaining | `python apps/api/scripts/run_imaging_contract_e2e.py` |
| Open-source governance gate | PASS_WITH_REVIEW_ITEMS; no vendored code/weights | `python apps/api/scripts/run_open_source_gate.py` |
| Synthetic WDI-20 E2E | PASS; 20 catalog entries and 6 Phase 1 workflows | `python apps/api/scripts/run_wdi20_e2e.py` |
| Phase 1 disease engine tests | PASS (58 tests); diabetes, hypertension, and CKD synthetic assessment contracts | `apps/api/tests/test_phase1_engine.py` |
| Phase 1 synthetic evaluation | PASS; 60 cases, 20 per disease; not clinical validation | `python apps/api/scripts/run_phase1_evaluation.py` |
| Synthetic evaluation | PASS (3 cases) | `python apps/api/scripts/run_eval.py` |
| Gemini real inference | BLOCKED if `GEMINI_API_KEY` is absent | `python apps/api/scripts/run_real_smoke.py` |
| MedGemma real inference | PASS for local Ollama `medgemma:latest`; default `medgemma:4b` is unavailable locally | `MEDGEMMA_MODEL=medgemma:latest python apps/api/scripts/run_real_smoke.py` |
| MedGemma decision-service E2E | PASS for synthetic request through `/v1/decisions`; no clinical efficacy claim | `MEDGEMMA_MODEL=medgemma:latest python apps/api/scripts/run_medgemma_decision_e2e.py` |
| MedGemma contract evaluation | PASS; 2 synthetic cases; no clinical accuracy claim | `MEDGEMMA_MODEL=medgemma:latest python apps/api/scripts/run_medgemma_contract_eval.py` |
| TRION real integration | BLOCKED: no verified endpoint/key in WyshCare | `python apps/api/scripts/run_real_smoke.py` |
| Secret-redaction/config tests | PASS (automated allowlist/redaction coverage) | `config.py`, `test_r1.py` |
| Signed gateway auth | PASS (valid, missing, expired, and wrong-tenant tokens) | `auth.py`, `test_r1.py` |
| Correlation IDs | PASS | `main.py`, `test_r1.py` |
| Evidence/provenance/audit | PASS | `decision.py`, `audit.py`, `test_r1.py` |
| Security release gate | PASS | `python apps/api/scripts/run_security_gate.py` |
| Model routing policy | PASS (cloud fallback denial tested) | `gateway.py`, `test_r1.py` |
| Model promotion allowlist | PASS (disabled-by-default and explicit enablement tested) | `config.py`, `gateway.py`, `test_r1.py` |
| TRION API boundary | PASS (typed contract, propagation, and disabled-path tests) | `trion_contract.py`, `main.py`, `test_r1.py` |
| Adversarial safety evaluation | PASS | `python apps/api/scripts/run_safety_eval.py` |
| Runtime model registry | PASS | `registry.py`, `GET /v1/models`, `test_r1.py` |
| Model promotion gate | PASS | `python apps/api/scripts/run_promotion_gate.py` |
| Full release checks | PASS_WITH_BLOCKED_REAL_INTEGRATIONS (Gemini/TRION unavailable) | `MEDGEMMA_MODEL=medgemma:latest python apps/api/scripts/run_release_checks.py` |
| Python wheel packaging | PASS; wheel contains packaged model registry | `python3 -m pip wheel --no-deps --no-build-isolation --wheel-dir /tmp/wysh-ai-wheel apps/api` |
| Patient/tenant isolation | PASS for existing synthetic prefix boundary | `test_api.py` |
| Synthetic Clinical Snapshot E2E | PASS | `python apps/api/scripts/run_clinical_snapshot_e2e.py` |
| Local provider HTTP E2E | PASS (synthetic loopback emulator only) | `python apps/api/scripts/run_local_provider_e2e.py` |
| Production isolation | PASS by default: production snapshot returns 503 | `test_api.py` |
| Runtime observability | PASS | `app/metrics.py`, `GET /metrics`, `test_r1.py` |

## Exact verification commands

```bash
cd apps/api
python -m pytest -q
MEDGEMMA_MODEL=medgemma:latest python scripts/run_real_smoke.py
MEDGEMMA_MODEL=medgemma:latest python scripts/run_medgemma_decision_e2e.py
MEDGEMMA_MODEL=medgemma:latest python scripts/run_medgemma_contract_eval.py
python scripts/run_local_provider_e2e.py
python scripts/run_promotion_gate.py
MEDGEMMA_MODEL=medgemma:latest python scripts/run_release_checks.py
```

The smoke command writes sanitized output to `artifacts/r1-test-evidence/real-provider-smoke.json`. It never writes credentials, prompts, raw model responses, or PHI.

## Completion assessment

R1 is **not complete** under the supplied completion criteria because real Gemini and real TRION evidence cannot be recorded without the required infrastructure/credentials or a verified endpoint contract. Real local MedGemma evidence is recorded for the explicitly configured `medgemma:latest` Ollama model. The independent synthetic API and fail-closed integration scaffolding are implemented; the remaining blocked integrations stay explicitly blocked rather than represented as passing.
