# Security and data policy

- Default implementation is synthetic-only, with no external model calls and no patient data; provider calls require explicit endpoint/credential configuration and model allowlisting.
- Production inference is explicitly disabled. `WMI_ENV=production` returns 503 for snapshots.
- Never expose API keys in browser or mobile clients. Do not log PHI or raw prompts.
- The typed decision service rejects common identifier keys and obvious email, phone, Aadhaar-like, and medical-record-number patterns in metadata; raw free-text/document fields are not an accepted substitute for typed evidence.
- Gemini credentials are sent in request headers, never URL query strings, to reduce proxy/access-log exposure.
- Audit identifiers are process-scoped keyed pseudonyms; raw tenant and patient identifiers must never enter an audit sink. Production deployments must replace the local sink and manage any stable pseudonym key through approved secret infrastructure.
- Correlation IDs accept only bounded opaque characters; invalid values are replaced before response headers or audit events to prevent log injection and accidental sensitive-data propagation.
- Provider base URLs are validated before gateway inference: only HTTP(S) endpoints without embedded credentials, query strings, or fragments are accepted; invalid configuration fails closed.
- Before PHI: require signed service authentication, scoped patient authorization, purpose/consent enforcement, regional/data-processing assessment, retention and deletion policies, audit and encryption.
- ABDM consent for healthcare exchange must not be presumed to authorize model training.
- Training data must have rights, lawful basis, provenance, patient-level de-identification review and isolation from evaluation data.
- Clinical outputs are drafts requiring clinician approval; no autonomous diagnosis, prescribing, or unreviewed record writes.
- TRION cannot independently override authorization or safety policies.
- JWKS and model-provider endpoints reject embedded credentials, query strings,
  fragments, and malformed schemes before any network request.
- Model routing order is allowlisted to the supported adapters; unknown route
  names fail closed during gateway configuration validation.
- Provider payloads are bounded before network I/O: requests are limited to
  64 KiB and responses to 1 MiB; oversized payloads are classified and fail
  closed without retries.
- The TRION boundary applies the same 64 KiB request and 1 MiB response
  limits, validates its endpoint configuration before I/O, and requires its
  typed `schemaVersion`/`generatedBy` response contract.
- Provider and TRION timeouts are capped at 120 seconds and adapter retries at
  five; invalid direct settings fail closed rather than creating an unbounded
  resource contract.
- TRION requests are replay-safe in the synthetic API lane: repeated
  idempotency keys return the original typed response, while conflicting
  content returns `409` before any downstream call.
- Public health/readiness responses expose provider configuration booleans and
  model identifiers only; internal endpoint URLs and credentials are not
  returned.
- Decision outputs are screened after typed parsing as well as before model
  invocation. Unsafe diagnosis, medication, treatment, emergency, or prompt
  injection language is converted to a non-diagnostic abstention.
- Synthetic idempotency caches are bounded LRU stores (1024 entries per API
  process), preventing unbounded replay-key memory growth. Eviction does not
  weaken the fail-closed conflict behavior for entries still retained.
- API responses are marked `no-store`/`no-cache`, `nosniff`, and
  `no-referrer` to prevent caching or browser interpretation of synthetic
  evidence and operational telemetry.
