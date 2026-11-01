# Phase 1–7 execution matrix

This matrix maps the requested AI program to executable wysh.AI evidence. It
does not convert engineering evidence into clinical authorization.

| Phase | Scope | Current evidence | Status | Closure evidence |
|---|---|---|---|---|
| 1 | Safety, security, interoperability | 179 backend tests, security isolation, FHIR/CQL contracts, authorization and audit | ENGINEERING PASS | Independent security assessment and authorized integration |
| 2 | Training, registry, A/B, evaluation | Governed synthetic datasets, lifecycle, ML operations, model hashes | ENGINEERING PASS | Rights-cleared data, external validation, signed promotion |
| 3 | Imaging research | DICOM/FHIR contracts, integrity checks, abstaining adapter | NON-DIAGNOSTIC ONLY | Licensed model, reader study, diagnostic validation |
| 4 | Clinical workflow/HITL | Persisted review, concurrency, provenance, human oversight | SYNTHETIC PASS | Authorized WyshCare integration and usability/security evidence |
| 5 | Clinical evidence | R15/R16 protocols and fail-closed gates | PREPARATION ONLY | Qualified reviewers, approved standards, permitted study |
| 6 | Regulatory and ethics | Readiness templates and risk register | NOT READY | Qualified Indian regulatory/privacy/ethics assessment |
| 7 | Release/open source/deployment | Release checks pass with blocked real integrations; OSS license gate blocked | NOT PUBLISHED / NO-GO | License owner approval, SBOM, rights review, signed release and deployment authorization |

## External research map

The repository records PhysioNet, OHDSI, WHO, and ICMR sources in
`research/external-evidence-catalog-v1.json`. Restricted datasets are not
downloaded or sent to external LLMs. PhysioNet access, training, and data-use
terms must be satisfied independently before any use.

## Current decision

Continue the engineering loop, but keep clinical governance `HOLD`, clinical
validation `NO-GO`, production `NO-GO`, and the score at 69/100 until the
external evidence gates are actually satisfied.
