# wysh.AI R14 clinical evidence governance

R14 remains an isolated engineering and research-readiness milestone. All
datasets and model prompts used in the evidence below are synthetic. No result
is a clinical performance claim or authorization for patient care.

## Intended use boundary

The current system may generate draft, evidence-linked engineering outputs for
synthetic evaluation. It must not diagnose, prescribe, recommend treatment,
trigger emergency action, or replace a qualified clinician. Deterministic
calculations and governed rules remain authoritative over model prose; model
failure produces abstention or unavailability, never a silent fixture result.

## Evidence lineage

- Challenge corpus: `research/medgemma/r13-challenge-corpus-v1.json`.
- Model safety evidence: `artifacts/r14-test-evidence/r14-medgemma-safety.json`.
- Statistical readiness: `artifacts/r13-test-evidence/r13-model-evaluation.json`.
- Imaging research evidence: `artifacts/r13-test-evidence/r13-imaging-research.json`.
- Reliability evidence: `artifacts/r14-test-evidence/r14-reliability.json`.

Each artifact records synthetic-only status, model identity where applicable,
schema/safety state, provenance or experiment identifiers, and clinical-use
authorization state.

## Review requirements

Before any clinical use, a qualified clinical reviewer and an independent
validation process must approve an intended-use statement, rights-cleared
representative dataset, statistical analysis plan, subgroup and calibration
protocol, safety case, risk controls, and applicable regulatory assessment.
Synthetic R14 evidence cannot satisfy those requirements.
