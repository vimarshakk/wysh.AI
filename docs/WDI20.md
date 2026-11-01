# WyshCare Disease Intelligence 20

WDI-20 is a shared disease-intelligence contract for patient, clinician, pharmacy, and research applications. It is not 20 separate AI products. Each condition references the same longitudinal measurement, evidence, review, authorization, and outcome-evaluation boundaries.

## Current implementation

- Catalog: `disease-intelligence/registry/disease-catalog.json`.
- Six Phase 1 workflow definitions: `disease-intelligence/conditions/phase1-workflows.json`.
- Shared contract: `disease-intelligence/shared/CONTRACT.md`.
- Catalog endpoint: `GET /v1/disease-intelligence/catalog`.
- Workflow endpoint: `GET /v1/disease-intelligence/workflows/{disease_id}`.
- Synthetic monitoring endpoint: `POST /v1/disease-intelligence/monitor`.
- Deterministic rule endpoint: `POST /v1/disease-intelligence/rules/evaluate`.
- Synthetic FHIR adapter: `POST /v1/disease-intelligence/fhir/monitor`.
- Synthetic E2E: `apps/api/scripts/run_wdi20_e2e.py`.

The monitoring engine reports only descriptive direction (`UP`, `DOWN`, `STABLE`, or `INSUFFICIENT_DATA`) for supplied measurements. It preserves measurement evidence references and reports missing data domains. It does not diagnose, assign risk, recommend treatment, issue prescriptions, escalate emergencies, or write back to an EHR/pharmacy system.

## Phase 1

Diabetes, prediabetes, hypertension, dyslipidemia, obesity, and chronic kidney disease are the first six packs because they share measurement, medication, renal, metabolic, and cardiovascular context. Their definitions are fully specified for data requirements, monitoring plans, four experience surfaces, workflow version, and clinical-rule status. Clinical rules remain disabled until separately validated.

## Evidence and population estimates

The catalog deliberately retains population scope notes and does not embed prevalence percentages into runtime behavior. Estimates from different denominators, years, study designs, or subpopulations must not be summed or treated as directly comparable. A future evidence registry must store source, denominator, year, uncertainty, and citation before any public claim is made.

Training is separate from care delivery. A patient record used for authorized care does not become training data unless it is separately consented, de-identified, licensed, governed, and approved.

See [WDI20_OPEN_SOURCE_ACCELERATION.md](WDI20_OPEN_SOURCE_ACCELERATION.md) for how disease-management projects informed the interfaces without being copied into the repository.
