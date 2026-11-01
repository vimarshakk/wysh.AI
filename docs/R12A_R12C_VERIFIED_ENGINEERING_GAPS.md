# wysh.AI R12A–R12C — Verified Engineering Gaps

R12 is an isolated synthetic engineering milestone. It does not establish clinical validity, production authorization, or regulatory readiness.

## R12A — Clinical model evaluation readiness

The evaluation layer now reports sample adequacy, class minimums, subgroup minimums, probability uncertainty summaries, alignment, and external-validation prerequisites. The current 20-row synthetic cohorts remain `INSUFFICIENT_SAMPLE`; no clinical performance score is manufactured and the scorecard delta is zero.

## R12B — Imaging research infrastructure

Local-only Orthanc, OHIF and MONAI service manifests define disabled-by-default synthetic prototypes, localhost-only endpoints, request timeouts, concurrency limits, and pixel budgets. The prototypes abstain and download no model weights. The existing R9 imaging safety boundary remains authoritative.

## R12C — Security and interoperability

An OpenFGA-style relationship parity harness compares candidate decisions with the canonical signed gateway policy, including revoked access. HAPI FHIR is represented as a synthetic R4 conformance contract, not a second server. Terminology is version-pinned in the contract while Snowstorm remains deferred pending distribution-rights and operational review.

Run the gate from `apps/api`:

```bash
PYTHONPATH=. ./.venv/bin/python scripts/run_r12_gate.py
```

Evidence is written to `artifacts/r12-test-evidence/r12-gate.json`. No WyshCare repository modification, PHI access, production service, external FHIR server, or model-weight download is performed.
