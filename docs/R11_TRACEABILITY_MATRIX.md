# R11 Traceability Matrix

| Requirement | Implementation | Verification | Evidence | Status |
| --- | --- | --- | --- | --- |
| Tenant/patient authorization | `apps/api/app/auth.py`, `apps/api/app/workbench.py` | `test_r11_hardening.py` | `r11-gate.json` | PASS |
| Purpose/consent/delegation | `apps/api/app/workbench.py` | authorization and delegated-access tests | `r11-gate.json` | PASS |
| Stale/concurrent review protection | `apps/api/app/review_store.py` | stale and terminal-state tests | `r11-gate.json` | PASS |
| Assessment replay protection | `apps/api/app/assessment_store.py` | version/replay tests | `r11-gate.json` | PASS |
| Prompt injection and unsupported claims | existing clinical safety plus R11 live gate | `test_r7c_orchestration.py`, live gate | `r11-live-safety.json` | BLOCKED if runtime unavailable |
| Performance/resource controls | provider settings and bounded authorization benchmark | `run_r11_gate.py` | `r11-gate.json` | PASS for measured local lane |
| Synthetic FHIR/ABDM compatibility | `apps/api/app/interoperability_contracts.py` | synthetic exchange tests | `r11-gate.json` | PASS |
| Reproducible evidence | versioned scripts and JSON artifacts | JSON validation and full pytest | `artifacts/r11-test-evidence/` | PASS |
| Clinical validation | outside isolated engineering scope | none | release metadata | NO-GO |
| Production deployment | explicitly unauthorized | none | release metadata | NO-GO |

Known unresolved risk: live MedGemma adversarial evaluation cannot be accepted until the local runtime/model is available. No fallback is permitted.
