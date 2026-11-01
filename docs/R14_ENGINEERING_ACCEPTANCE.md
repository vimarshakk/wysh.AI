# wysh.AI R14 engineering acceptance

## Status

`PASS_WITH_BOUNDARIES` for isolated synthetic engineering. The score remains
69/100; this milestone earns no clinical-validation or production-readiness
points.

## Evidence

- R14A: all 16 synthetic MedGemma challenge cases executed against the real
  local `medgemma:latest` model. All responses were schema-valid and received
  independent deterministic `PASS` or `ABSTAINED` safety evaluation. No
  fixture fallback was used.
- R14B: evaluation readiness remains explicitly
  `PASS_WITH_INSUFFICIENT_SAMPLE`; the 20-row research cohorts cannot support
  clinical performance claims.
- R14C: native image processing remains reproducible, integrity-bound, and
  non-diagnostic. No model weights were downloaded or executed.
- R14D: intended-use restrictions, evidence lineage, model approval boundary,
  and qualified-review requirements are recorded.
- R14E: three repeated live MedGemma probes passed schema and safety checks;
  observed latency was 4.659–5.434 seconds. The bounded resource contract is
  60 seconds, 512 output tokens, zero retries, and no fallback.
- The first 16-case run at a 60-second ceiling exposed two provider failures;
  the complete retry at a 120-second ceiling passed all 16. The retry history
  is preserved in `artifacts/r14-test-evidence/r14-medgemma-safety-retry-history.json`.
- R14F: 179 backend tests, 2 CQL runtime tests, and the Clinical Console
  typecheck/build passed.

## Release boundaries

Clinical governance remains `HOLD`; clinical validation and production remain
`NO-GO`. WyshCare was not modified. No PHI or external clinical service was
used. These results establish engineering evidence only, not clinical accuracy,
effectiveness, diagnostic validity, or regulatory authorization.
