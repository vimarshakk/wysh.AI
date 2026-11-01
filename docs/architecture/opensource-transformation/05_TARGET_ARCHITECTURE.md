# Target Architecture

FastAPI remains the primary orchestration boundary. Domain modules stay in-process while high-risk external runtimes remain optional isolated services.

1. Clinical intelligence core: evidence registry, disease packs, deterministic calculations, rule engine, provenance, safety, governance, patient review.
2. Interoperability: synthetic FHIR R4 adapters, code/unit mapping, future terminology boundary, consent/auth contracts.
3. Medical AI: local MedGemma adapter, provider registry, structured output validation, model/version audit, abstention.
4. Research: synthetic dataset registry, evaluation artifacts, future experiment/model lineage.
5. Experience: Clinical Console reads backend truth and displays governance status without simulating approval.

The CQL/FHIR vertical slice is a seam, not a second server: it can later be replaced by a pinned CQF/Blaze service without changing the console or rule-governance contracts.
