# Contributing to wysh.AI

wysh.AI is an isolated, preclinical engineering project. Contributions must
preserve synthetic-only execution and the distinction between engineering
evidence, clinician review, and clinical validation.

## Before opening a change

- Do not include PHI, production identifiers, credentials, proprietary prompts,
  restricted datasets, or model weights.
- Keep new fixtures explicitly synthetic and keep provenance references typed.
- Do not add silent provider fallback, autonomous diagnosis, prescribing,
  emergency action, or unreviewed record writes.
- Do not mark a model, rule, or imaging adapter clinically approved from a
  unit test or synthetic result.
- Record upstream projects as reference-only or adapter-only unless their code
  and runtime are actually integrated and their license is verified.

## Verification

From `apps/api`, run:

```bash
./.venv/bin/pytest -q
./.venv/bin/python scripts/run_objective_gate.py
```

If local MedGemma is available, run the live synthetic gates documented in
`docs/R7D_REAL_LOCAL_MEDGEMMA.md`. Missing credentials or endpoints must remain
explicitly `BLOCKED`; do not replace them with fixtures.

## Clinical and security review

Changes affecting authorization, provenance, model routing, safety filters,
clinical rules, CQL, imaging, or review persistence require negative tests and
documentation of the remaining clinical and production restrictions.
