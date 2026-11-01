# WDI-20 integration boundaries

## Ownership

- **WyshCare owns:** identity, tenants, consent, clinical records, FHIR/ABDM exchange, prescriptions, pharmacy operations, notifications, user-facing workflows, and authoritative state changes.
- **wysh.AI owns:** model routing, synthetic fixtures, typed intelligence contracts, evidence/provenance metadata, bounded deterministic rules, evaluation harnesses, and draft recommendations.
- **Clinicians own:** review, acceptance, modification, rejection, escalation, and patient-facing clinical decisions.

## Request boundary

The integration must use a versioned request envelope containing a scoped service identity, tenant context, consent/access context, minimum necessary clinical data, requested task, provenance, and synthetic/live environment marker. No direct database reads, raw credential forwarding, or implicit patient identity propagation is allowed.

## Response boundary

Every response must identify model/provider mode, evidence references, uncertainty/abstention state, review requirement, and whether any action was merely drafted or actually committed. wysh.AI must not write prescriptions, diagnoses, referrals, or ABDM records directly.

## Safety boundary

Local synthetic validation may proceed. Live Gemini, TRION, ABDM, cloud deployment, and PHI-connected testing remain separate gates and are not prerequisites for building the contracts, fixtures, and evaluation harness.
