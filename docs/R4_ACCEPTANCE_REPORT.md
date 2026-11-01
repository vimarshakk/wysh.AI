# wysh.AI R4 isolated engineering acceptance

Date: 2026-10-24

Overall status: **ENGINEERING PASS / CLINICAL VALIDATION NO-GO / PRODUCTION NO-GO**

## Verification baseline

- Existing backend baseline was re-run before implementation: the prior 65-test baseline remains green, with 68 tests currently passing after R4A coverage was present.
- Final backend suite after R4B and R4C: **72 passed**.
- The only test warning is the existing Starlette/httpx deprecation warning.

## R4 milestones

### R4A — review integrity: PASS

Authenticated synthetic clinician review is persisted locally with role and
tenant/patient authorization, immutable event history, and optimistic
concurrency. Approve, reject, and request-revision transitions are covered by
negative tests. The Clinical Console no longer presents UI-only approval as a
clinical decision.

### R4B — verified calculations: PASS for engineering scope

The three Phase-1 workflows now have transparent calculation contracts:

- Diabetes: descriptive mean glucose and ADA HbA1c-to-eAG calculation.
- Hypertension: descriptive mean systolic/diastolic and paired pulse pressure.
- CKD: CKD-EPI 2021 creatinine eGFR when adult age, sex, and standardized creatinine are present; otherwise abstention.

Reference vectors are stored in
`fixtures/synthetic/clinical-calculations/r4b-reference-vectors.json` and are
independently tested. These outputs do not diagnose, classify risk, recommend
treatment, prescribe, refer, or write a clinical record.

### R4C — executable CQL boundary: PASS for bounded subset

No external CQL runtime or external clinical content was installed. A pinned,
allowlisted synthetic subset executes only `count-facts`, `mean-numeric`, and
`has-glucose` under `wysh.synthetic.rules.v1`. Unknown libraries and
expressions remain `UNCONFIGURED`; arbitrary code and clinical thresholds are
not accepted. This is not a full CQL implementation.

### R4D — integrated verification: PASS

`apps/api/scripts/run_r4_integrated_e2e.py` passed console patient discovery,
synthetic assessment provenance, verified calculations, bounded CQL execution,
persisted review creation, and persisted review decision retrieval.

The local MedGemma gateway and contract evaluation passed using
`medgemma:latest` with synthetic administrative workflow prompts only. No
clinical accuracy claim is made.

The Clinical Console TypeScript check and Next.js production build passed.

## Evidence

- [R4A acceptance](R4A_CLINICAL_REVIEW_ACCEPTANCE.md)
- [Integrated R4 E2E](../artifacts/r4-test-evidence/r4-integrated-e2e.json)
- [R4A evidence](../artifacts/r4-test-evidence/r4a-acceptance.json)
- [MedGemma decision evidence](../artifacts/r1-test-evidence/medgemma-decision-e2e.json)
- [MedGemma contract evidence](../artifacts/r1-test-evidence/medgemma-contract-evaluation.json)

## Release boundary

This completes isolated R4 engineering only. Clinical validation remains
blocked pending prospective/retrospective clinical evaluation, reference-data
review, clinician governance, privacy/security controls, and authorized
WyshCare integration. Production deployment, PHI processing, cloud fallback,
Gemini, TRION, and protected-branch operations remain disabled.
