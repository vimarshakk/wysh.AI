# wysh.AI — WMI-1

Standalone, safety-first clinical intelligence service for WyshCare. **Preclinical engineering scaffold, not approved for patient care.**

Contribution and security rules are documented in [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## Scope
- Track A: governed multimodel clinical snapshot API, evidence references, human-review lifecycle, model registry, TRION tool boundary.
- Track B: independently governed model adaptation, dataset manifests, evaluation and promotion gates.
- No autonomous diagnosis, prescribing, or EHR writes.

## Local setup
```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest
uvicorn app.main:app --reload
```

Generate an isolated example with `POST /v1/snapshots` and synthetic patient context. The API defaults to disabled inference and rejects PHI-like requests without an authorized gateway context. It does not contact model providers.

## WyshCare integration
NestJS must authenticate users, resolve patient authorization and consent, minimize context, and mint a short-lived signed service token. When `WMI_REQUIRE_GATEWAY_AUTH=true`, `wysh.AI` validates the token algorithm, issuer, audience, expiry, tenant, patient scope, route scope, practitioner identity, purpose, consent and delegated-access claims **before** invoking any inference. Development remains synthetic-only and can run without a token for local iteration; production remains inference-disabled until the deployment gates are approved.

## Current implementation status
- [x] Repository scaffold, versioned API schema, basic snapshot contracts
- [x] Explicit synthetic-only development boundary, deny-by-default production mode
- [x] Model registry manifest, explicit runtime model allowlist, and deterministic no-inference stub
- [x] Tests for schema, synthetic boundary, and review gating
- [x] Local signed service-token verification boundary and synthetic scope tests
- [x] TRION adapter contract with authenticated headers and response validation (live endpoint blocked)
- [x] MedGemma, Gemini, and OpenAI-compatible self-hosted adapters (local MedGemma connectivity verified; other real endpoints remain gated)
- [x] Loopback HTTP E2E harness for provider/TRION contracts, explicitly separate from real-provider evidence
- [x] Evidence-grounded typed decisions, abstention policy, provenance, redacted audit, and low-cardinality metrics
- [x] Real local MedGemma request through the typed decision gateway (synthetic-only, human review required)
- [x] JWKS-backed RS256 verification (WyshCare consent policy integration still required)
- [ ] Calibrated decision model and clinical evaluation
- [ ] Dataset governance, fine-tuning and independent validation
- [x] Synthetic Clinical Snapshot → decision E2E and security isolation gates
- [x] R2 preparation contracts, synthetic FHIR fixture, clinician review handoff, and provenance gate
- [x] Imaging contract with metadata-only validation, synthetic abstention E2E, and open-source adoption matrix

## Current synthetic engineering evidence

- 179 backend tests passing.
- Real local `medgemma:latest` orchestration verified with no fixture fallback.
- 16/16 adversarial MedGemma cases schema-validated and safety-evaluated.
- Aggregate release suite: `PASS_WITH_BLOCKED_REAL_INTEGRATIONS`.
- Gemini, OpenAI-compatible, and TRION live connectivity remain explicitly
  credential/endpoint gated.
- Clinical validation and production deployment remain `NO-GO`.

Run the aggregate gate from `apps/api`:

```bash
./.venv/bin/python scripts/run_objective_gate.py
```
- [x] Adapter-only open-source governance ledger and license/model-weight promotion gate
- [x] WDI-20 disease catalog and six Phase 1 synthetic longitudinal-care workflows
- [ ] Production clinical E2E, clinical evaluation, and release approval

See `docs/IMPLEMENTATION.md` and `docs/SECURITY.md`.

## License & Ownership

wysh.AI is proprietary to **Wysh Care Technologies Private Limited (WyshCare)**.
All rights reserved. See `LICENSE`. This software is preclinical engineering,
not approved for patient care, and is governed by WyshCare audit and clinical
safety boundaries.

For self-hosted endpoint setup, see `docs/integration/OPEN_SOURCE_ENDPOINTS.md`.
