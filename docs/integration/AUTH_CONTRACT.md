# WyshCare → wysh.AI gateway authorization contract

The intended topology is WyshCare authenticating the user, resolving consent and patient access, minimizing context, then issuing a short-lived service token to `wysh.AI`. `wysh.AI` does not authenticate end users and does not mint tokens.

## Required token

The boundary accepts a signed JWT with either the local HS256 mode or the preferred RS256/JWKS mode. RS256 is the intended deployment mode; HS256 is retained for isolated local testing.

Required JWT properties:

- `typ: JWT` and an explicitly configured algorithm: `HS256` or `RS256` (algorithm is pinned; `none`, algorithm switching, and unconfigured algorithms are rejected)
- RS256 tokens require a `kid` and a matching RSA key in `SERVICE_TOKEN_JWKS_URL`; JWKS documents are cached for the configured TTL and are never logged.
- `iss` equal to `SERVICE_TOKEN_ISSUER`
- `aud` equal to `SERVICE_TOKEN_AUDIENCE`
- integer `iat` and future `exp`
- non-empty `sub`
- `tenant_id` equal to the request tenant
- `patient_ids` containing the request patient or `*`
- `scope` containing the route permission

Route scopes:

- `/v1/snapshots`: `snapshot:write`
- `/v1/decisions`: `decision:execute`
- `/v1/integration/wyshcare/clinical-draft`: `clinical-workflow:execute`

The WyshCare clinical-draft bridge additionally binds the signed token to the
request's `practitioner_subject`, `purpose_of_use`, `consent_id` and optional
`delegated_by` values. The token must carry a clinician or clinical-reviewer
role. Matching tenant and patient scope alone is not sufficient.

Missing, malformed, expired, incorrectly signed, incorrectly scoped, or incorrectly addressed tokens return `401` without exposing the reason or token material.

## Deployment boundary

Development remains unauthenticated only when `WMI_REQUIRE_GATEWAY_AUTH=false` and `WMI_ENV=development`, and it still accepts synthetic identifiers only. Non-development environments require gateway authorization and keep clinical inference disabled until the safety gates are explicitly approved.

Before PHI processing, use RS256/JWKS with a managed issuer, key rotation, TLS and network allowlisting, and verify WyshCare’s exact issuer and audience values in an isolated integration environment.
