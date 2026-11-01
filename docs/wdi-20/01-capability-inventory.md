# WDI-20 capability inventory

| Capability | Current owner/location | Status | Integration work |
|---|---|---|---|
| Authentication and tenant boundaries | WyshCare backend/core | Existing | Accept only a scoped service token; never duplicate identity state |
| Consent and access control | WyshCare consent modules/core contracts | Existing | Require consent/access context on clinical requests |
| Patient timeline and health graph | WyshCare timeline/health-graph modules | Existing | Export minimum necessary, typed observations |
| Prescriptions and pharmacy workflows | WyshCare prescription/pharmacy modules | Existing | AI may draft/explain; WyshCare remains authoritative |
| FHIR/ABDM integration | WyshCare core/ABDM modules; wysh.AI synthetic FHIR adapter | Partial | Agree on profile/version and provenance envelope |
| Model provider gateway | wysh.AI `apps/api/app/providers.py` and `gateway.py` | Local implemented | Gemini/TRION remain explicitly deferred |
| WDI-20 disease catalog | wysh.AI `disease-intelligence/registry` | Implemented catalog | Add governance metadata and clinical review |
| Six Phase-1 workflow definitions | wysh.AI `disease-intelligence/conditions` | Implemented definitions | Connect to WyshCare workflows only after contract review |
| Descriptive longitudinal monitoring | wysh.AI `disease_intelligence.py` | Implemented, synthetic | Expand measurements only through reviewed schemas |
| Deterministic completeness rules | wysh.AI `clinical_rules.py` | Partial | Threshold/risk logic is intentionally not enabled |
| Imaging metadata/report draft contract | wysh.AI `imaging.py` | Implemented draft-only | No image bytes, masks, diagnosis, or autonomous action |
| Clinician review UI | WyshCare frontend | Existing platform surface, AI integration pending | Add explicit review/action provenance |
| Patient experience UI | WyshCare frontend | Existing platform surface, AI integration pending | Add education and escalation states |
| Training pipeline | Not yet implemented | Not started | Build reproducible, licensed-data-only pipeline |
| Clinical evaluation | Synthetic contract tests only | Not started | Create reviewable cases and adjudication process |
| TRION live integration | Unknown pending contract inspection | Blocked/deferred | Do not invent endpoint or auth contract |
