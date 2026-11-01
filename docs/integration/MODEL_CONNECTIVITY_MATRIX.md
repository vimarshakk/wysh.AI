# R1 model connectivity matrix

Inspection date: 2026-10-24 (Asia/Kolkata). All requests in this repository are synthetic-only.

| Integration | WyshCare contract / discovered configuration | wysh.AI implementation | Evidence status |
|---|---|---|---|
| Gemini | `GEMINI_API_KEY`, `GEMINI_MODEL` (default in WyshCare source: `gemini-2.5-flash`); WyshCare adapter uses Google Generative AI SDK | `GeminiProvider`; JSON structured output, Pydantic validation, bounded retries, timeout, token telemetry | BLOCKED until `GEMINI_API_KEY` is explicitly supplied; run `python apps/api/scripts/run_real_smoke.py` |
| MedGemma | `MEDGEMMA_MODEL` (default `medgemma:4b`); `OLLAMA_HOST` then `OLLAMA_URL`; WyshCare adapter calls Ollama `/api/chat` | `MedGemmaProvider`; readiness verifies the configured model is listed by `/api/tags`, then sends Ollama JSON-schema requests with Pydantic validation, bounded retries, and timeout | PASS for local Ollama `medgemma:latest` with synthetic request; default `medgemma:4b` remains unavailable in the local tag inventory |
| Open-source compatible endpoint | `OPENAI_COMPATIBLE_BASE_URL`, `OPENAI_COMPATIBLE_MODEL`, optional API key/path | `OpenAICompatibleProvider`; supports vLLM, llama.cpp servers, and compatible gateways through `/v1/chat/completions` | READY FOR CONFIGURATION; no endpoint was present locally, so no real request was claimed |
| TRION | WyshCare `fhirDraftSchema`: `schemaVersion: 1`, `generatedBy: TRION`; env names `TRION_ENABLED`, `TRION_BASE_URL`, `TRION_API_KEY`, `TRION_MODEL`, `TRION_TIMEOUT_MS` | `TrionClient`; bearer auth, correlation ID, idempotency key, fail-closed response validation | BLOCKED: no TRION client/service or non-empty API key was found in WyshCare |
| Decision service | No existing WyshCare endpoint found; existing policy boundary is draft/review-only | `/v1/decisions`; explicit permitted options, synthetic-only policy, abstention, model/policy IDs, evidence refs, redacted telemetry, idempotency and conflict rejection | PASS for disabled-inference abstention, policy, replay and provenance tests; no clinical calibration claim |

## Security bridge

`GET /v1/models/readiness` exposes redacted provider readiness. It does not
probe cloud providers by default; `probe_local=true` is an explicit local-only
probe for configured MedGemma or OpenAI-compatible endpoints. Readiness never
implies clinical approval or clinical-use authorization.

Only the allowlisted names in `apps/api/app/config.py` can be read from an explicitly supplied env file. The loader does not load the WyshCare `.env` automatically and never copies database, Firebase, ABDM, encryption, or unrelated variables. Secret values are not returned by `/health`, telemetry, test output, or exceptions.

Gateway authorization is independently enforced when `WMI_REQUIRE_GATEWAY_AUTH=true`: signed tokens must satisfy issuer, audience, expiry, tenant, patient, and route-scope checks before request processing.

The decision API defaults to `provider=auto`, which uses the configured local-first routing order. Cloud Gemini fallback is disabled by default and must be explicitly enabled with `ALLOW_CLOUD_FALLBACK=true`; there is no silent cloud fallback.

Provider credentials are not sufficient to invoke a model. The model must be manifest-enabled and its runtime ID must also be present in `MODEL_ENABLED_IDS`; an empty allowlist or disabled manifest entry denies all gateway inference. `clinical_approved` remains a separate promotion gate and is not implied by technical connectivity.

The read-only `GET /v1/models` endpoint exposes manifest status, clinical approval status, and runtime allowlisting only; it never returns credentials or provider secrets.
