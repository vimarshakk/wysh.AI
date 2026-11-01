# wysh.AI R8C–R8E Research and Model Governance

R8C–R8E is an isolated, synthetic-only engineering milestone. It does not establish clinical effectiveness, clinical validation, regulatory clearance, or production readiness.

## R8C research baselines

The repository contains reproducible CPU-friendly baselines for three disease-oriented cohorts:

- diabetes: `wysh.synthetic.diabetes.review.v1`
- hypertension: `wysh.synthetic.hypertension.review.v1`
- CKD: `wysh.synthetic.ckd.review.v1`

Each cohort has a versioned registry entry, original synthetic rows, SHA-256 provenance, patient-level deterministic splitting, an explicit synthetic engineering target, a 30-day engineering horizon, an index date, a feature cutoff, an eligibility statement, and an abstention policy. The labels are generated for pipeline testing and are not clinical outcomes.

Run the gate from `apps/api`:

```bash
PYTHONPATH=. ./.venv/bin/python scripts/run_r8cde_gate.py
```

The gate writes model experiment manifests to `artifacts/r8-models/` and the sanitized report to `artifacts/r8-test-evidence/r8cde-gate.json`.

## R8D evaluation contract

`app/research_evaluation.py` provides dependency-free AUROC, AUPRC, Brier score, calibration error, bootstrap confidence intervals, subgroup checks, patient-group and temporal leakage checks, and missing-data/OOD checks. Metrics requiring more evidence return `INSUFFICIENT_SAMPLE`; they do not emit a misleading estimate. The current 20-row cohorts therefore remain engineering diagnostics only.

## R8E lifecycle

Models move through:

`EXPERIMENTAL → ENGINEERING_VERIFIED → CLINICAL_REVIEW_PENDING → CLINICALLY_APPROVED`

The lifecycle store requires evidence for engineering verification and a qualified reviewer identity for clinical-review pending. `CLINICALLY_APPROVED` is deliberately rejected by the engineering API; it requires an external qualified governance process. Synthetic tests cannot authorize clinical use.

## Safety and release boundary

All datasets and artifacts are synthetic-only and non-PHI. No external data, PHI, production credentials, WyshCare code, or production services are accessed. Clinical governance remains `HOLD`, clinical validation is `NO-GO`, and production is `NO-GO`.
