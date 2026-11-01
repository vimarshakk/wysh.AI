# R13A–R13D model and imaging research

R13 is an isolated synthetic engineering milestone. No clinical performance or diagnostic validity is claimed.

## Disease baselines

Diabetes, hypertension, and CKD each execute the governed logistic baseline plus a transparent constant-prevalence comparator. Both artifacts include dataset and registry hashes, deterministic patient-group splits, seeds, split counts, and `clinical_use_authorized=false`. The 20-row cohorts remain `INSUFFICIENT_SAMPLE` for meaningful clinical evaluation.

Evaluation readiness now reports class adequacy, subgroup adequacy, uncertainty summaries, alignment, and external-validation prerequisites. One-class, empty, nonfinite, and malformed metric inputs fail explicitly.

## Imaging research path

R13 adds a tiny native synthetic pixel-integrity/descriptive-statistics task. It verifies dimensions, bounded pixel values, subject marker, and pixel hash, then returns non-diagnostic statistics only. Corrupt hashes and dimension mismatches abstain. No MONAI, Orthanc, OHIF, nnU-Net, or MedSAM weights were downloaded or executed.

## MedGemma challenge result

The versioned corpus contains 16 synthetic adversarial categories; 8 were executed against the real local `medgemma:latest` model. All 8 cases returned schema-valid output and deterministic `PASS` or `ABSTAINED` safety states. The response budget and prompt were tightened after the first run exposed a truncation/schema failure; no fixture fallback was used. The remaining 8 corpus cases are retained for a future expanded safety run.

R13D is `PASS` for the executed 8-case engineering subset. This does not establish
clinical safety, clinical effectiveness, or approval for patient care.
