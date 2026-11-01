# wysh.AI R6B — Rule Execution and Governance Acceptance

Status: **ENGINEERING PASS** · **CLINICAL GOVERNANCE HOLD** · **CLINICAL VALIDATION NO-GO** · **PRODUCTION NO-GO**

R6B adds a synthetic, isolated rule-governance lifecycle for versioned clinical rules:

`DRAFT → REVIEWED → APPROVED → ACTIVE → REVOKED/EXPIRED`

Rule governance is deliberately separate from patient assessment review. A clinician's review of an individual synthetic assessment cannot approve a rule, and a rule approval cannot approve a patient assessment. The rule record contains no patient identifier and binds approval to an exact evidence identifier, rule version, revision hash, expiry, reviewer role, expected version, and immutable event history.

The API requires strict bearer authentication for governance routes, synthetic tenant scope, and separate roles/scopes for rule engineering, clinical review, and governance activation/revocation. Stale versions, replayed transitions, evidence substitution, expired rules, and cross-tenant access fail closed.

The diabetes hypoglycemia vertical slice now handles unit normalization, inclusive threshold boundaries, same-timestamp conflicts, duplicate readings, invalid assessment timestamps, and stale evidence when an explicit assessment time is supplied. Its output is explicitly `OBSERVATION_CLASSIFICATION_ONLY`; it never represents an episode diagnosis, treatment decision, emergency instruction, or clinical authorization. The evaluator remains `ENGINEERING_ONLY` even if a synthetic governance fixture reaches `ACTIVE`.

## Evidence

- Backend R6B tests are run with `apps/api/.venv/bin/pytest -q`.
- Synthetic gate: `apps/api/scripts/run_r6b_governance_gate.py`.
- Gate output: `artifacts/r6-test-evidence/r6b-governance-gate.json`.
- The CQL capability remains the existing restricted, allowlisted synthetic contract; this milestone does not claim general CQL/ELM interoperability.

No qualified clinical reviewer approval is fabricated or written into the evidence registry. Clinical validation, WyshCare integration, external model connectivity, and production deployment remain out of scope.
