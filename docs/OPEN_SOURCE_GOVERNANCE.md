# Open-source and model governance

This repository uses external open-source projects as documented integration references. It does not copy their source code, UI assets, sample data, model weights, prompts, or documentation into Wysh.AI.

## Non-negotiable rules

1. External projects are adapter-only or reference-only. A repository is not a dependency merely because it appears in research notes.
2. Every project is recorded in `packages/contracts/open-source-adoption-v1.json` with its source URL, role, integration mode, code-license status, model-weight status, and promotion status.
3. Unverified code licenses and model-weight terms cannot be promoted to a runtime dependency or model registry entry.
4. Model weights are governed separately from source code. A permissive code license does not imply permissive model-weight, dataset, or commercial-use terms.
5. If code is ever imported, preserve the complete upstream license and notices, pin an immutable version, generate an SBOM, and record security review evidence before merge.
6. Screenshots, icons, fonts, datasets, clinical images, and prompts require their own provenance record; public availability is not a license.
7. Wysh.AI-generated adapters and contracts remain original work and must not reproduce upstream implementation text.

The local `run_open_source_gate.py` command checks the ledger for these invariants. It reports review items without treating them as approved dependencies. This is an engineering control, not legal advice; counsel should review any future redistribution, hosted service, or commercial model-weight decision.

Current disease-management reuse decisions are deliberately conservative: Nightscout is a reference for glucose ingestion and time-series UX, Bahmni/OpenMRS and OpenEMR are workflow references, and AHRQ CQL Services is an adapter candidate for standards-based deterministic rules. Nightscout is AGPL-3.0 and OpenEMR is GPL-3.0, so their source is not copied into this project. AHRQ CQL Services is Apache-2.0, but its runtime is still not installed; Wysh.AI currently exposes an original rule interface instead.
