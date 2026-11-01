# R15 risk management

## Hazard register

| Hazard | Control | Residual status |
|---|---|---|
| Unsupported diagnosis or treatment advice | Typed output, deterministic safety checks, abstention, draft-only review | Requires independent clinical safety validation |
| Fabricated or cross-patient evidence | Evidence allowlisting, provenance hashes, tenant/patient authorization | Synthetic scope only |
| Dataset leakage or rights failure | Governed manifests, group/temporal splits, rights metadata | Representative rights-cleared data absent |
| Model drift or version substitution | Pinned model identity, versioned artifacts, registry gates | Monitoring plan not operational |
| Timeout/resource exhaustion | Bounded output, timeout, retry and no-fallback contract | Sustained-load testing pending |
| Imaging misinterpretation | Integrity checks and explicit non-diagnostic abstention | Diagnostic validity not established |
| Reviewer bias or conflict | Independent qualifications, COI disclosure, adjudication protocol | Reviewers not appointed |
| Privacy or security incident | Synthetic-only ingress, authorization and audit controls | Production PHI assessment not authorized |

Residual risks require qualified governance review before any clinical study or
deployment decision.
