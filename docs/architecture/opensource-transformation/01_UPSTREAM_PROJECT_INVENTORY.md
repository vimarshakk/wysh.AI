# Upstream Project Inventory

The machine-readable inventory is [upstream-project-inventory.json](/Users/vimarshakprudhvi/Downloads/wysh.AI/artifacts/opensource-transformation/upstream-project-inventory.json). It records 34 candidate repositories/organizations from the CTO mandate, an adoption decision, rationale, canonical URL, and whether source/licensing verification is still required.

The current adoption categories are `INTEGRATED`, `ADAPTED`/`ADAPT_ARCHITECTURE`, `REFERENCE_ONLY`, `PLANNED`, `RESEARCH_ONLY`, and `REJECT`. `cql-execution` and `cql-exec-fhir` are now genuinely `INTEGRATED` in an isolated runtime lane; this does not mean all 34 projects are integrated.

The targeted primary-source review covered CQF CQL Execution, CQF Clinical Reasoning, CQF Ruler, CQL FHIR execution, and Blaze. The review found that CQL Execution consumes JSON ELM, requires separate data-model and terminology providers, and documents incomplete feature coverage; CQF Ruler is migrating functionality toward HAPI; and Blaze exposes FHIR R4/CQL operations. Those findings support an isolated adapter decision, not wholesale dependency installation.

All other candidates remain explicit reference, research, or blocked adoption decisions until their current source, license, dependency, security, and maintenance state is independently verified.
