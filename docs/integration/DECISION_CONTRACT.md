# Non-diagnostic decision contract

`POST /v1/decisions` is intentionally limited to synthetic workflow routing. It is not a diagnostic, prescribing, triage, emergency, or treatment endpoint.

## Request invariants

- `question` is explicit and bounded.
- `provider` defaults to `auto`, which follows the configured local-first model routing order; explicit provider selection remains available for controlled tests.
- `tenant_id` and `patient_id` are explicit typed fields; they cannot be smuggled through untyped context.
- `permitted_options` contains at least two unique options.
- `synthetic` must be `true` in the current R1 policy.
- `evidence` contains typed source references; raw clinical documents are not accepted by this endpoint.
- `application_profile` is restricted to `clinician-copilot`, `care-navigation`, or `operations`; a patient-companion profile cannot invoke workflow decisions.
- A non-abstaining output requires at least one typed evidence reference; otherwise the policy layer forces abstention.
- `context` is limited to at most 20 scalar workflow-metadata fields, with bounded string values; nested objects and raw document payloads are rejected. It is used only to construct the request hash and provider prompt and is never included in audit events.

## Response invariants

- `selected_option` is either one of the permitted options or `null`.
- Invalid model selections are converted to abstention.
- Abstentions always have `confidence: null`.
- `provenance.input_hash` is a SHA-256 hash of the canonical request shape; raw request content is not persisted in the audit sink.
- `provenance.model_id`, `policy_version`, `correlation_id`, and evidence count are always present.
- `human_review_required` remains true and `clinical_use_authorized` remains false.

Raw model confidence is discarded in R1. Before exposing confidence to clinical users, it needs a preregistered calibration and subgroup validation study.
