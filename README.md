# wysh.AI 

Standalone, safety-first clinical intelligence service for WyshCare. **Preclinical engineering — not approved for patient care.**

[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![Pydantic](https://img.shields.io/badge/Pydantic-2.8-orange.svg)](https://docs.pydantic.dev/)
[![Tests](https://img.shields.io/badge/tests-185%20passing-brightgreen.svg)](apps/api/tests/)
[![Objective Gate](https://img.shields.io/badge/objective_gate-PASS_WITH_BOUNDARIES-blue.svg)](apps/api/scripts/run_objective_gate.py)
[![CI](https://img.shields.io/github/actions/workflow/status/vimarshakk/wysh.AI/.github/workflows/ci.yml?branch=master)](.github/workflows/ci.yml)

wysh.AI is a standalone clinical intelligence scaffold that runs synthetic patient snapshots through governed decision gates. It evaluates typed clinical facts, enforces deny-by-default inference, and emits structured routing decisions — no autonomous diagnosis, no prescribing, no EHR writes.

## Why wysh.AI?

- **Safety first.** Deny-by-default production mode. Inference disabled until deployment gates approve.
- **Synthetic only.** Tenant and patient IDs must start with `synthetic-`. No PHI accepted without authorized gateway context.
- **Gateway-authenticated.** JWKS RS256 service-token verification validates issuer, audience, expiry, tenant, patient scope, route scope, practitioner identity, purpose, consent, and delegated access before inference.
- **Model governance.** Versioned model registry with explicit runtime allowlist. No registry model is clinically approved.
- **Human-review lifecycle.** Typed decisions carry abstention policy, provenance, redacted audit, and low-cardinality metrics.
- **TRION boundary.** WyshCare TRION adapter contract with authenticated headers and response validation (live endpoint blocked).

## Architecture

| Component | Role |
|-----------|------|
| gateway | Authenticated entry; service-token validation |
| auth | Token claims: issuer, audience, expiry, tenant, scope, practitioner, consent |
| decision | Typed clinical decisions with abstention policy |
| clinical_engine | Snapshot orchestration |
| registry | Model registry (EXPERIMENTAL only) |
| model_lifecycle | Registry transitions; clinical approval blocked |
| providers | MedGemma, OpenAI-compatible, Gemini adapters |
| trion | WyshCare TRION adapter contract |
| audit | Redacted audit logging with input hashing |
| review_store | Human-review lifecycle store |
| assessment_store | Assessment persistence |
| metrics | Low-cardinality metrics |
| replay_cache | Replay cache for idempotency |
| imaging | Metadata-only imaging contract |
| capabilities | Versioned capability exposure |
| disease_specific_intelligence | Disease packs (diabetes, hypertension, CKD) |
| standards_cql | CQL standards integration |
| verified_calculations | Deterministic clinical calculations |
| workbench | Engineering workbench |
| console_contracts | Console integration contracts |
| research_evaluation | Research model evaluation |
| reuse_accelerator | Reuse accelerator |

## What's Inside

- **`apps/api/app/`** — Python FastAPI service: gateway, auth, decision, providers, imaging, audit, review, metrics, and more.
- **`apps/api/tests/`** — 185 backend tests covering schema, synthetic boundary, review gating, token verification, and more.
- **`research/`** — Disease catalog, epidemiology sources, external evidence catalog, MedGemma challenge corpus, model registry.
- **`artifacts/`** — R1–R2 test evidence gates: synthetic evaluation, security gate, clinical snapshot E2E, MedGemma contract/decision E2E, imaging contract E2E, phase 1 evaluation, provenance gate.
- **`docs/`** — R1–R17 clinical evidence, governance, validation, regulatory specs; implementation, platform architecture, security.

## Quick Start

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest
uvicorn app.main:app --reload
```

Generate an isolated example with `POST /v1/snapshots` and synthetic patient context. The API defaults to disabled inference and rejects PHI-like requests without an authorized gateway context. It does not contact model providers.

Run the aggregate gate:

```bash
./.venv/bin/python scripts/run_objective_gate.py
```

## ⚠️ Preclinical — Not for Patient Care

wysh.AI is preclinical engineering. It is **not approved for patient care**. Clinical validation is `NO-GO`. Production deployment is `NO-GO`. Do not use for autonomous diagnosis, prescribing, or EHR writes.

## Contribute

We welcome issues, bug reports, and pull requests.

### Good First Issues
Look for issues labeled `good first issue`. Common starting points:
- Add schema validation tests for new snapshot fields
- Write synthetic boundary tests for a new provider adapter
- Add disease pack validation for the WDI-20 catalog
- Improve README examples and quick-start steps

### PR Flow
1. Fork the repo and create a branch from `master`
2. Make your change and add tests
3. Run `pytest` from `apps/api` and confirm green
4. Open a PR against `master` with a clear description
5. A maintainer will review and merge

## Roadmap

- [ ] P1: Calibrated decision model and clinical evaluation
- [ ] P2: Dataset governance, fine-tuning, and independent validation
- [ ] P3: Production clinical E2E and release approval gates
- [ ] P4: MedGemma/OpenAI-compatible live endpoint verification
- [ ] P5: R3–R17 clinical evidence completion
- [ ] P6: Imaging contract production hardening
- [ ] P7: Deployment gate approval workflow

## Call to Action

If wysh.AI looks useful, **star** the repo, **fork** it, and **open an issue**. Let's build governed clinical intelligence together — publicly, and safely.

---

*wysh.AI is preclinical engineering. It is not approved for patient care. See `SECURITY.md` and `SECURITY` contribution guidelines before handling any health data.*
