# WDI-20 repository baseline

**Snapshot date:** 2026-10-24 (Asia/Kolkata)  
**Scope:** local engineering validation only. No production systems, patient data, or external model credentials were used.

## Repositories inspected

### wysh.AI

The working repository is a standalone Python/FastAPI model-intelligence layer. It currently contains:

- a local-first provider gateway with strict provider allowlisting;
- typed clinical snapshot, decision, imaging, provenance, and audit contracts;
- synthetic WDI-20 disease catalog and six Phase-1 workflow definitions;
- deterministic descriptive monitoring and completeness rules;
- synthetic FHIR Observation ingestion for a deliberately small, explicit code map;
- local evaluation and contract E2E scripts.

The local test suite currently reports **52 passing tests**. This is an engineering result, not clinical validation or a release approval.

### WyshCare

`/Users/vimarshakprudhvi/wyshcare` was inspected read-only at git HEAD `6856d461`. The monorepo includes a NestJS backend, Prisma persistence, Firebase integration, a frontend, shared/core contracts, ABDM integration, and domain modules covering identity, consent, timeline/health graph, prescriptions, pharmacy, emergency flows, notifications, and related platform capabilities.

The inspection did not edit WyshCare, start production services, read secrets, access PHI, or call Gemini/TRION/ABDM production endpoints.

## Integration conclusion

WyshCare is the system of record and workflow surface. wysh.AI is a bounded intelligence service. The safe integration shape is a typed, authenticated gateway carrying minimum necessary data, with provenance and review state returned explicitly. Direct database coupling and silent model writes are out of scope.

## Evidence limitations

The WDI-20 burden figures supplied in planning material are retained as unverified research inputs only. They are not imported into runtime logic, and no disease prevalence, diagnostic, treatment, or risk claim is asserted by this baseline.
