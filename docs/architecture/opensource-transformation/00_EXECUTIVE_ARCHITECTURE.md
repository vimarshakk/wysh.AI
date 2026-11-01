# wysh.AI Open-Source Transformation — Executive Architecture

This workstream keeps FastAPI as the orchestration boundary and adds capability through isolated, provenance-bearing adapters. The governing rule is: reuse architecture and standards patterns; do not copy clinical content, model weights, or source code without a license decision.

Current engineering target:

`synthetic FHIR R4 Bundle → typed Observation mapping → pinned JSON ELM shape → fail-closed evaluation → evidence refs/hash → rule governance → patient review`

The new standards slice is intentionally bounded to one diabetes observation-presence expression. It is not general CQL conformance and does not activate clinical use. The existing rule-governance lifecycle remains separate from patient-level clinician review.

Architecture decisions:

- ADAPT_ARCHITECTURE: CQF/CQL execution, CDS Hooks, local inference, sensitive-data minimization.
- ISOLATED_SERVICE: a future pinned CQL runtime or FHIR server, only after dependency/license/security review.
- REFERENCE_ONLY: large EHR, terminology, orchestration, and workflow projects that would duplicate current boundaries.
- RESEARCH_ONLY: predictive ML and imaging projects; no clinical model claims are enabled.
- REJECT: unnecessary orchestration or an unverified dependency.
