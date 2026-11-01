# System One Decision Model Architecture

wysh.AI now includes a **System One decision model** — a fast, deterministic,
probabilistic routing engine that takes structured clinical facts and emits
structured routing decisions. It is deliberately **not** a conversational LLM.

## Design principle

System Two models (LLMs, MedGemma) generate text token-by-token, burn compute,
and risk hallucinating formatting or claims. A System One decision model acts
like a high-speed routing engine or structured form-checker: bounded input,
bounded output, deterministic inference, no text generation on the hot path.

MedGemma and other System Two providers remain available through the existing
decision service but are **never on the System One hot path**.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    System One Decision Router               │
│  ┌─────────────┬─────────────────┬───────────────────────┐ │
│  │  Feature    │  Routing Engine │  Decision Model       │ │
│  │  Extractor  │                 │  (logistic /          │ │
│  │             │                 │  threshold rules)     │ │
│  └─────────────┴─────────────────┴───────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
        ▲                    ▲                    ▲
 Structured          Model         Structured
 clinical facts      selection     routing decision
 (typed evidence)    by indication (action, confidence,
                     abstention)
```

### 1. Feature Extractor (`apps/api/app/feature_extractor.py`)

Typed clinical facts (observations, conditions, medications, encounters) are
converted into a bounded numeric feature vector:

- **Deterministic**: same input → same feature vector, every time
- **Bounded**: max 500 facts, values clamped to [0, 1e6], no raw documents
- **No PHI**: patient names, MRNs, emails, phones, addresses rejected
- **Output**: feature names, values, missing-metric flags, input hash

### 2. Decision Model (`apps/api/app/decision_model.py`)

Lightweight model performing fast structured inference:

- **Primary**: R8B logistic-regression baseline (dependency-free, CPU-friendly,
  weights + standardization loaded from experiment manifest)
- **Fallback**: transparent threshold rules per indication (HbA1c ≥ 6.5 → review,
  BP systolic ≥ 180 → escalate, eGFR ≤ 30 → escalate, etc.)
- **Output**: selected action, calibrated confidence, reason, model path
- **No text generation**: no rationale strings, no explanations, no claims

### 3. Routing Engine (`apps/api/app/routing_engine.py`)

Probabilistic model selection with bounded fallback:

- Model selected by indication (diabetes → diabetes model, etc.)
- Bounded fallback chain (max 3 attempts)
- Route attempts recorded (model, path, status, latency, reason)
- Unknown indication → abstention
- Missing required metrics → abstention

### 4. System One Router (`apps/api/app/system_one_router.py`)

Main entry point. Structured input → structured output:

- **Synthetic-only**: tenant/patient IDs must start with `synthetic-`
- **No PHI**: context rejects names, MRNs, emails, phones, addresses
- **Deny by default**: `clinical_use_authorized = false`, `human_review_required = true`
- **Model must be CLINICALLY_APPROVED** for any clinical use authorization
- **No autonomous diagnosis, prescribing, or treatment**

## Safety boundaries

| Boundary | Enforcement |
|---|---|
| Synthetic only | tenant/patient IDs must start with `synthetic-` |
| No PHI | context rejects identifiers and raw text fields |
| Deny by default | `clinical_use_authorized` is `false` unless model is `CLINICALLY_APPROVED` |
| Human review | `human_review_required` is always `true` |
| Missing data | abstention when required metrics are absent |
| No diagnosis | output is routing action only, never a diagnosis or treatment |
| Fail closed | routing failures → abstention, never a silent wrong answer |

## Model registry

`research/models/model-registry-v1.json` registers three System One decision
models, all `EXPERIMENTAL`:

- `wysh.synthetic.diabetes.review.v1`
- `wysh.synthetic.hypertension.review.v1`
- `wysh.synthetic.ckd.review.v1`

No automated or synthetic workflow can set `CLINICALLY_APPROVED` — that
requires an external qualified governance process (see `model_lifecycle.py`).

## Test results

- 25 new System One tests: all passing
- Full suite: 210 passed (185 pre-existing + 25 new)

## What remains

- Real training pipeline (R8C/R8D: not started — synthetic contract tests only)
- Calibration study before exposing confidence to clinicians
- External validation on representative data
- Independent clinical review and governance approval before `CLINICALLY_APPROVED`
