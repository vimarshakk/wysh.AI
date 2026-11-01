# wysh.AI R9A/R9B — Imaging Contracts and Adapter Boundary

R9A/R9B is isolated, synthetic-only imaging engineering. It does not establish diagnostic performance, clinical validation, regulatory clearance, or production readiness.

## R9A contract

`app/imaging_research.py` defines a synthetic DICOM metadata contract and a FHIR R4 `ImagingStudy` contract. The contract records modality, body region, transfer syntax, content hash, synthetic subject reference, de-identification method, and provenance hashes. It never accepts raw image bytes, URLs, local paths, or PHI.

The de-identification gate fails closed unless the synthetic marker, synthetic subject reference, UIDs, and de-identification method are present. Source and FHIR resource hashes are retained as separate provenance fields.

## R9B adapters

The adapter boundary is modality/task-neutral and returns only draft or abstained results. The built-in unconfigured adapter always abstains. The MONAI research adapter only reports whether the optional `monai` package is installed; it does not download packages, download weights, load unapproved weights, or emit clinical findings. Even when MONAI is installed, it abstains until a model, modality, license, task configuration, and evaluation evidence are separately approved.

Run the gate from `apps/api`:

```bash
PYTHONPATH=. ./.venv/bin/python scripts/run_r9ab_gate.py
```

Evidence is written to `artifacts/r9-test-evidence/r9ab-gate.json`.

## Release boundary

`clinical_use_authorized` remains false. Clinical governance is `HOLD`, clinical validation is `NO-GO`, and production is `NO-GO`. The existing metadata-only `/v1/imaging/analyze` API remains unchanged and continues to abstain when no validated model is configured.
