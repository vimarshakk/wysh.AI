# R8A/R8B Dataset Governance and Reproducible Training

R8A and R8B introduce an isolated research lane under `research/datasets` and `apps/api/app/ml_governance.py`.

The registered dataset is original synthetic data created in this repository. The registry records its rights owner, license basis, source type, synthetic-only and non-PHI assertions, allowed/prohibited uses, feature/label schemas, split policy, and provenance chain. Loading fails closed when the dataset is unregistered, missing, outside the repository, not explicitly synthetic, or missing rights metadata.

R8B uses a dependency-free logistic-regression baseline so the experiment is CPU-friendly and reproducible. The training manifest captures the dataset and registry SHA-256 digests, seed, features, label, hyperparameters, deterministic group split, leakage result, standardization statistics, model weights, metrics, and a provenance hash. The label is `synthetic_review_required`, an engineering label only; it is not a diagnosis, risk prediction, treatment target, or clinical outcome.

Run the experiment from `apps/api`:

```sh
./.venv/bin/python scripts/run_r8b_baseline.py
```

Outputs:

- `artifacts/r8-test-evidence/r8b-experiment.json`
- `artifacts/r8-models/<experiment-id>.json`

The artifacts are research evidence only. No PHI is accepted, no external dataset is downloaded, and `clinical_use_authorized` remains false. R8C/R8D will require separate disease-specific research design, calibration, subgroup analysis, uncertainty evaluation, and governance review.
