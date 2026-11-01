# Security and Clinical Safety

Implemented controls include synthetic tenant/patient gates, signed bearer verification, role/scope separation, optimistic concurrency, evidence binding, expiry/revocation, immutable event history, no patient identifiers in rule governance, and fail-closed unsupported ELM.

Clinical boundaries remain explicit:

- Rule approval is separate from assessment approval.
- Numeric observation classification is not a diagnosis or episode.
- Unapproved rules remain `ENGINEERING_ONLY`.
- CQL subset output cannot prescribe, refer, escalate, or write records.
- No PHI or production endpoint is admitted.

Remaining controls for a production or clinical-validation path include managed identity/JWKS operations, append-only protected audit storage, terminology licensing and validation, formal CQL conformance, reviewer credential governance, clinical reference review, and prospective clinical evaluation.
