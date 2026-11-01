# Contributing to wysh.AI

## Scope & Boundaries

wysh.AI is preclinical engineering. It is **not approved for patient care**.
- No autonomous diagnosis, prescribing, or EHR writes.
- Synthetic-only development context.
- Deny-by-default production inference.
- No automated or synthetic workflow can set `CLINICALLY_APPROVED` in the model registry.

## How to Contribute

### Issues
- Report bugs, schema gaps, or safety concerns
- Use labels: `bug`, `feature`, `good first issue`, `documentation`, `safety`, `synthetic-only`

### Pull Requests
1. Fork the repository
2. Create a feature branch from `master`
3. Implement your change and add tests
4. Run `pytest` from `apps/api` and confirm green
5. Open a PR against `master` with a clear description
6. A maintainer will review and merge

### PR Template Checklist
- [ ] Tests added or updated
- [ ] `pytest` passes from `apps/api`
- [ ] No PHI introduced in tests or fixtures
- [ ] Synthetic-only boundary preserved
- [ ] Documentation updated (if applicable)

## Modules

gateway, auth, decision, clinical_engine, registry, model_lifecycle, ml_governance, providers, multimodal_orchestration, trion, bridge, interoperability_contracts, imaging, audit, review_store, assessment_store, metrics, replay_cache, disease_specific_intelligence, standards_cql, verified_calculations, workbench, console_contracts, research_evaluation, reuse_accelerator

## Adapters

MedGemma, Gemini, OpenAI-compatible, TRION

## Security

- Do not submit PHI in issues or PRs.
- All synthetic data must use `synthetic-` prefixed identifiers.
- Report security concerns privately per `SECURITY.md`.

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Questions?

Open an issue or start a discussion. We respond quickly.