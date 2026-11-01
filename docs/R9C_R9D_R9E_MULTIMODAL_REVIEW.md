# wysh.AI R9C–R9E — Multimodal Safety and Review

R9C–R9E is synthetic-only isolated engineering. It does not establish imaging diagnostic performance, clinical validity, regulatory clearance, or production readiness.

## R9C multimodal evidence envelope

`app/multimodal_orchestration.py` combines an existing structured clinical workflow status with an independent imaging modality envelope. Imaging source hash, FHIR resource hash, model identity, model version, uncertainty, modality status, and safety checks remain separate from clinical FHIR/CQL/MedGemma provenance.

If the imaging adapter returns `ABSTAINED` or is unavailable, the envelope exposes imaging as `ABSTAINED` with no findings. It never converts the absence of imaging output into a negative imaging finding. Structured clinical analysis may retain its own status.

## R9D fail-closed safety

The safety gate checks synthetic de-identification metadata, subject consistency, optional pixel-hash integrity, and timestamp syntax. Subject mismatch, corrupt hashes, invalid timestamps, unsupported modality contracts, and unconfigured adapters abstain. No raw image bytes or PHI enter the workflow.

## R9E clinician review

`MultimodalReviewService` binds the evidence-envelope provenance hash to the existing persistent `ReviewStore`. Draft creation and approval/rejection/revision events are emitted through the existing append-only audit sink. Review approval records human review of a synthetic draft; it does not authorize the imaging model or clinical use.

Run the gate from `apps/api`:

```bash
PYTHONPATH=. ./.venv/bin/python scripts/run_r9cde_gate.py
```

Evidence is written to `artifacts/r9-test-evidence/r9cde-gate.json`.

Clinical governance remains `HOLD`, clinical validation is `NO-GO`, and production is `NO-GO`.
