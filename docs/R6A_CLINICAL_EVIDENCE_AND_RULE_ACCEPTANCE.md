# R6A — Clinical evidence registry and rule vertical slice

Status: **ENGINEERING PASS / CLINICAL GOVERNANCE HOLD / CLINICAL VALIDATION NO-GO / PRODUCTION NO-GO**

Implemented:

- Versioned source-metadata registry with publisher, version, jurisdiction,
  applicability, observations, terminology, limitations, licensing metadata,
  and reviewer/expiry fields.
- Original diabetes hypoglycemia observation rule contract.
- Unit normalization for mg/dL and mmol/L.
- Boundary tests for the configured engineering boundaries.
- Missing-evidence abstention, disease-scope abstention, provenance, and
  blocked actions.
- API endpoint:
  `POST /v1/disease-intelligence/approved-rules/evaluate`

The rule emits a clinician-review finding only. It never diagnoses, predicts
risk, prescribes, changes treatment, sends a referral, or gives emergency
instructions. The evidence entry is intentionally marked `ENGINEERING_ONLY`
with no reviewer identity because none has been supplied. It must not be
promoted to `CLINICALLY_REVIEWED` without qualified clinical governance.

Evidence: `artifacts/r6-test-evidence/r6a-rule-gate.json`.

Historical evidence is preserved. The repository had 81 passing tests at the
start of R6; the current suite has 84 after adding the R6A tests.
