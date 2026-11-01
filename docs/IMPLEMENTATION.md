# WMI-1 implementation roadmap

## Track A — Platform (12-week engineering target)
1. R0: Audit WyshCare TRION and AI Orchestrator, freeze ownership and contracts, model licenses, threat model, intended use.
2. R1: Signed service-to-service auth (JWKS, iss/aud, short TTL), tenant/patient/action scope and consent verification; deny by default.
3. R2: TRION tool registry with per-tool permissions, timeouts, idempotency and approval gates. Never let LLM authorize tools.
4. R3: MedGemma private inference and Gemini approved-provider adapters behind a policy-aware gateway. No PHI fallback without approval.
5. R4: Evidence-grounded snapshot with source IDs, time/version, abstention and clinician review. No direct EHR writes.
6. R5: Typed decision engine, calibrated on held-out cases; no autonomous triage/diagnosis.
7. R6: Web/Flutter/iOS integration through WyshCare NestJS; isolated browser E2E, security, clinical validation, performance and rollback.

## Track B — Model (6-month research target)
1. Intended use and rights-cleared dataset manifest; patient-level splits and contamination checks.
2. Frozen base checkpoint and reproducible benchmark against MedGemma baseline.
3. LoRA/QLoRA adapter training with approved datasets and immutable run metadata.
4. Independent clinician-blinded evaluations; errors, omissions, subgroup and abstention tests.
5. Quantization/serving benchmarks; shadow evaluation against Track A.
6. Model card, license notices, risk register, approval and reversible promotion.

## Cross-track gates
G0 inventory; G1 security; G2 provider governance; G3 data rights; G4 evidence provenance; G5 clinical evaluation; G6 TRION approval; G7 reliability; G8 full E2E; G9 independent sign-off.
All mandatory gates must pass. No AWS ECS deployment until the full relevant test suite passes.
