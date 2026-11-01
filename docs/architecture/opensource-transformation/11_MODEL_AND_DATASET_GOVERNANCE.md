# Model and Dataset Governance

No new training, fine-tuning, predictive model, PHI dataset, or external medical corpus was introduced. Existing MedGemma use remains local and synthetic-only under the existing model registry and safety contracts.

Future adoption of PyHealth, OHDSI, MONAI, MLflow, DVC, vLLM, or Haystack requires: exact release pinning, license review, dataset provenance, patient-level/temporal split checks, model card, calibration and subgroup evaluation, prompt/data leakage tests, and explicit promotion gates.
