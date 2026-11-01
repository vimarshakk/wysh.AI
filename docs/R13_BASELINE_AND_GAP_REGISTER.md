# R13 baseline and verified gap register

Baseline inspected before R13 changes. Scope is the writable `wysh.AI` repository only; WyshCare is read-only and remains unmodified.

| Capability | Source evidence | Tests/evidence | Current limitation | R13 change | Risk | Acceptance |
| --- | --- | --- | --- | --- | --- | --- |
| Governed disease datasets | `apps/api/app/ml_governance.py`, `research/datasets/registry-v1.json` | R8 governance, R8CDE gate | Three 20-row synthetic cohorts; no clinical outcome validity | Add comparator manifests and readiness reporting | Medium | Reproducible logistic/comparator runs; adequacy remains `INSUFFICIENT_SAMPLE` |
| Evaluation metrics | `apps/api/app/research_evaluation.py` | R8 tests | Core metrics exist; pathological/reference coverage incomplete | Add PPV/NPV, calibration applicability and pathological fixtures | High | Invalid inputs never become favorable scores |
| Imaging contracts | `apps/api/app/imaging_research.py`, `imaging_infrastructure.py` | R9/R12 gates | Adapter boundary abstains; no actual image-processing execution | Add tiny native synthetic pixel-integrity research task | High | Non-diagnostic execution only; corrupt/oversize/mismatch abstains |
| MedGemma safety | `scripts/run_r11_live_safety_gate.py` | R11 live artifact | Three live adversarial cases | Add versioned challenge corpus and expanded live subset | High | Actual local model only; no fixture fallback |
| Open-source adoption | `controlled-adoption-backlog.json`, inventory | R12 gate | Reference/adapt decisions are not upstream integrations | Add field-level adoption decisions for R13 candidates | Medium | `INTEGRATED` only when runtime is genuinely executed |
| Authorization and review | `auth.py`, `workbench.py`, `review_store.py`, `assessment_store.py` | R11/R12/R10 tests | Synthetic-only; external WyshCare parity not authorized | Preserve contracts and test R13 regressions | High | No cross-tenant, replay, or stale approval bypass |
| Clinical readiness | scorecard and release artifacts | R11/R12 gates | Clinical validation, regulatory and production gates are closed | No R13 claim; retain score | Critical | Score remains 69 unless existing criteria are independently met |

## Baseline result

- Backend: 128 passing before R13 edits.
- CQL runtime: 2 passing.
- R12 gate: PASS; scorecard delta 0.
- R11 real MedGemma adversarial gate: PASS, no fixture fallback.
- Imaging diagnostic inference: not established.
- Clinical governance: HOLD; clinical validation and production: NO-GO.

No R13 work changes WyshCare, accesses PHI, downloads large weights, adds an external service, or modifies protected branches.
