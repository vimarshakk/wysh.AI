# Execution Roadmap

## R6C — standards seam (current)

One synthetic FHIR R4 Observation to allowlisted JSON ELM expression, with provenance and fail-closed behavior. Engineering PASS; clinical governance HOLD.

## R7A — isolated runtime integration (current)

Pinned `cql-execution` and `cql-exec-fhir` packages execute the synthetic FHIR R4/ELM fixture through a local subprocess bridge. Engineering PASS; the integration is still allowlisted and not a general CQL service.

## R7B — standards conformance

Run the upstream CQL test suite and selected FHIR/ELM fixtures in a separate compatibility lane, then add terminology contract and FHIR validation. No production or clinical activation.

## R8 — governed model evaluation

Synthetic dataset registry, model cards, temporal split checks, safety evaluation, and reproducible local MedGemma evidence.

## R9 — research imaging and longitudinal ML

Only isolated, licensed, synthetic/non-PHI research workflows. No diagnostic claims.

Each phase must preserve the existing clinical-use and deployment NO-GO gates until independently reviewed.
