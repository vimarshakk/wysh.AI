# R1 TRION contracts

The inspected WyshCare source contains a versioned `fhirDraftSchema`, but no TRION network client or endpoint implementation. This document therefore defines the narrow adapter boundary without claiming a live TRION integration.

## Request boundary

`POST {TRION_BASE_URL}{TRION_PATH}` where `TRION_PATH` defaults to `/v1/clinical/fhir-draft`.

Headers:

- `Authorization: Bearer <server-side TRION_API_KEY>`
- `X-Correlation-Id: <request correlation ID>`
- `Idempotency-Key: <stable retry key>`
- `Content-Type: application/json`

The request is an opaque JSON object until the verified TRION endpoint contract is supplied. The client is disabled unless `TRION_ENABLED=true` and both endpoint and API key are present.

The local API boundary is `POST /v1/trion/fhir-draft`. It accepts a typed synthetic request, forwards a versioned draft envelope, propagates the request correlation ID and caller idempotency key, and requires the route scope `trion:fhir-draft` when gateway auth is enabled.

When gateway authentication is enabled, the request must also bind the signed
WyshCare context to the practitioner subject, clinician role, purpose of use,
consent ID and optional delegated-access subject. Missing or mismatched context
is rejected before the TRION client is invoked.

## Response boundary

The response must satisfy the WyshCare contract:

```json
{
  "schemaVersion": 1,
  "documentId": "synthetic-document-id",
  "resources": [],
  "generatedBy": "TRION",
  "model": "optional-model-id"
}
```

The adapter rejects other schema versions, missing `generatedBy`, non-2xx responses, timeouts, invalid JSON, and missing credentials. It does not persist drafts or authorize EHR writes.

## Open integration blockers

The verified WyshCare checkout has no TRION service/client implementation and its `.env` has an empty `TRION_API_KEY`. A real request must not be attempted until the service owner supplies the endpoint path, authentication audience/issuer requirements, and a synthetic-only test environment.
