# Implementation Backlog

Completed in this increment:

- R6B governed rule lifecycle and negative security tests.
- Synthetic FHIR R4 + JSON ELM vertical slice.
- Evidence hash and source-reference boundaries.
- Console read-only rule governance status.
- Source inventory and upstream adoption decisions.

Next dependency-ordered work:

1. Pin and evaluate a standards CQL runtime in an isolated Node/Java lane; run CQL test fixtures before any integration claim.
2. Add terminology provider contract with versioned synthetic ValueSets; do not load licensed terminology content.
3. Add rule artifact packaging and ELM schema validation.
4. Expand disease-specific deterministic rules only after clinical reference review.
5. Add model/dataset governance artifacts before predictive or imaging research.
