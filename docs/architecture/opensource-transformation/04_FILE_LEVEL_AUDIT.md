# File-Level Audit

The reconciled inventory is [file-audit.json](/Users/vimarshakprudhvi/Downloads/wysh.AI/artifacts/opensource-transformation/file-audit.json). It enumerates relevant files under `apps/api/app`, `apps/api/tests`, the Clinical Console source, disease intelligence, contracts, fixtures, and docs while excluding generated caches, dependency trees, build outputs, and graph caches.

R6B/R6C audit focus:

- `apps/api/app/rule_governance_store.py`: persistent, versioned rule lifecycle; synthetic-only and separate from patient reviews.
- `apps/api/app/approved_clinical_rules.py`: observation classification with abstention, units, conflicts, duplicates, and provenance.
- `apps/api/app/fhir_adapter.py`: allowlisted FHIR R4 Observation mapping.
- `apps/api/app/standards_cql.py`: original fail-closed JSON ELM subset boundary.
- `apps/api/app/main.py`: API and authorization boundary.
- `apps/api/tests`: negative, boundary, governance, and standards tests.
- `apps/clinical-console/lib/api.ts` and `apps/clinical-console/app/page.tsx`: backend-derived governance status only.

The generator records the exact file count and paths; future audits should diff that artifact rather than claim silent complete coverage.
