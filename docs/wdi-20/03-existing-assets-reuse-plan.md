# Existing asset reuse plan

| Existing asset | Reuse decision | Reason |
|---|---|---|
| WyshCare identity/tenant/consent | Integrate by contract | Prevent duplicate security and consent state |
| WyshCare timeline/health graph | Integrate by typed export | Preserve longitudinal context without database coupling |
| WyshCare FHIR/ABDM modules | Adapter boundary | Keep exchange and compliance ownership in WyshCare |
| WyshCare prescriptions/pharmacy | Human-reviewed draft integration | AI must not become an autonomous ordering system |
| wysh.AI provider gateway | Reuse | Already local-first and fail-closed |
| wysh.AI provenance/audit contracts | Reuse | Supports traceability and sanitized evidence |
| Open-source projects in the research register | Learn patterns or build adapters | No source-code or model-weight vendoring without license review |
| External endpoints | Defer | Credentials, contracts, residency, and data-processing controls are unresolved |

The implementation rule is **learn, specify, and reimplement cleanly**. Copying source code, weights, datasets, branding, or undocumented APIs is not part of this program.
