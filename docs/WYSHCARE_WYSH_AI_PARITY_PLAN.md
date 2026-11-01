# WyshCare × wysh.AI capability parity and upgrade plan

This is a read-only repository comparison performed on 2026-10-24. No WyshCare
files were modified. The two systems should not be made identical: WyshCare is
the operational care platform; wysh.AI is the governed clinical-intelligence
plane.

## Verified engineering snapshot

The comparison was rechecked against the current source trees and wysh.AI's
aggregate gate on 2026-10-24:

| Evidence | Result | Interpretation |
|---|---|---|
| wysh.AI backend regression | 179 passed, 1 warning | Local engineering regression is green |
| wysh.AI aggregate objective gate | `PASS_WITH_BOUNDARIES` | Required synthetic and security evidence is present |
| Live local MedGemma evidence | `PASS` | Real local inference evidence is current; fixture fallback is disallowed |
| Clinical Console | Typecheck and production build pass | Workbench is locally buildable |
| Bridge and WyshCare emulator lane | `PASS` | Contract behavior is verified without production integration |
| Clinical use | Disabled | No clinical authorization is implied |
| Clinical validation | `NO-GO` | No independent clinical study has been established |
| Production deployment | `NO-GO` | No production release is authorized |
| WyshCare source changes | None made by this comparison | WyshCare remains read-only |

Authoritative evidence is recorded in
`artifacts/objective-gate/objective-gate.json` and the linked R7D/R14
artifacts. These results prove isolated engineering behavior, not clinical
efficacy, regulatory clearance, or production readiness.

## Executive comparison

| Capability | WyshCare | wysh.AI | Current leader | Upgrade direction |
|---|---|---|---|---|
| Patient/doctor operational workflows | Extensive NestJS modules, Flutter SDKs, mobile/web workflows, scheduling, pharmacy, prescriptions, billing, messaging | Independent Clinical Console and typed workbench | WyshCare | Keep operational ownership in WyshCare; consume governed AI drafts through a contract |
| Identity, consent, tenant/patient access | Auth, MFA, patient scope, consent, ABDM/HIE flows, access grants, break-glass controls | Signed gateway-token validation and synthetic authorization parity | WyshCare for real operations; wysh.AI for fail-closed AI boundary | WyshCare authorizes; wysh.AI independently verifies scoped tokens and purpose |
| FHIR/ABDM interoperability | Production-oriented FHIR/ABDM/NHCX modules and exchange flows | Synthetic FHIR R4, CQL/FHIR runtime, terminology and provenance contracts | WyshCare operationally; wysh.AI analytically | Publish one versioned contract; add conformance tests on both sides |
| AI providers | OpenAI, Gemini, Ollama, MedGemma, NVIDIA/OpenRouter adapters and orchestrator | MedGemma, Gemini, OpenAI-compatible, TRION boundary; typed gateway and no silent fallback | wysh.AI safety boundary; WyshCare provider breadth | Route clinical intelligence through wysh.AI; retain WyshCare AI for non-clinical productivity until migrated |
| Clinical disease intelligence | Many domain modules and risk assessors; evidence and validation status need consolidation | Diabetes, hypertension, CKD advanced workflows; WDI-20 registry and contracts | wysh.AI governance; WyshCare breadth of product surfaces | Move disease logic into governed packs and expose draft results to WyshCare |
| ML training/serving | Separate `ml/` service with XGBoost, sklearn/ONNX, feature SQL, no-show/engagement/churn | CPU reproducible baselines, model lifecycle, registry, A/B, drift/review contracts | WyshCare operational ML execution; wysh.AI governance | Connect through versioned model manifests; do not merge clinical and operational targets |
| CQL/rules/terminology | Clinical rules exist across modules; standard CQL conformance is not the central execution path | Pinned `cql-execution` + `cql-exec-fhir`, bounded synthetic rules, terminology and rule governance | wysh.AI | Make wysh.AI the governed rule-evaluation plane; WyshCare consumes signed findings |
| Imaging | Imaging module, FHIR/audit/preview/jobs/providers; production workflow surface exists | DICOM/ImagingStudy contracts, integrity checks, explicit abstention, no diagnostic weights | WyshCare workflow; wysh.AI safety contract | Add research adapter in wysh.AI first; never expose diagnostic output without validation |
| Human review/audit | Clinical audit, document review, draft services, event store and workflow persistence | Persistent clinician review, evidence/model binding, immutable synthetic audit | Both; different scopes | WyshCare owns operational record; wysh.AI owns AI provenance and draft lifecycle |
| Evaluation/governance | Broad test/release evidence, but clinical-AI scorecard is not unified with wysh.AI | R1–R16 evidence, 69/100 score, synthetic safety, validation-readiness gates | wysh.AI | Publish one cross-repository traceability and release gate |
| Open-source posture | LICENSE.md and large operational repository; third-party/deployment surface requires review | Conservative adoption ledger, no confirmed license file, release gate blocked on license owner | WyshCare has a license; wysh.AI has stronger adoption controls | Confirm Wysh.AI copyright/license, SBOM, notices, model/data rights before publication |

## What WyshCare is ahead in

1. Real product workflows and operational persistence.
2. Authentication, MFA, patient identity, consent, ABDM, HIE, and exchange.
3. Doctor and patient experiences across web, Flutter, and iOS surfaces.
4. Operational ML service infrastructure and database-backed feature extraction.
5. Imaging, prescription, emergency, pharmacy, messaging, billing, and clinic
   operations.

WyshCare is the system of record and workflow system. It should not become the
place where ungoverned clinical model logic is duplicated.

## What wysh.AI is ahead in

1. Typed clinical-intelligence boundaries and model routing.
2. Explicit abstention, evidence references, provenance, and no-fallback rules.
3. Pinned CQL/FHIR execution and terminology contracts.
4. Synthetic disease packs and reproducible evaluation gates.
5. Model lifecycle separation from clinician assessment approval.
6. MedGemma safety corpus and real local inference evidence.
7. Research-only imaging abstention and integrity contracts.
8. Validation-readiness and clinical-governance artifacts.

wysh.AI is the governed intelligence plane. It should not absorb WyshCare’s
identity, billing, consent, or operational database responsibilities.

## Gaps shared by both

- No independent clinical validation for the intended uses.
- No qualified external clinical reviewer evidence in the repository.
- No approved rights-cleared representative dataset.
- No completed Indian ethics/regulatory applicability decision.
- No production-grade sustained-load evidence for clinical AI.
- No authorized WyshCare-to-wysh.AI production integration.
- Imaging diagnostic validity is not established.
- wysh.AI open-source publication is blocked pending license-owner and rights
  confirmation.

## Upgrade sequence

### Upgrade ownership matrix

| Workstream | WyshCare upgrade | wysh.AI upgrade | Exit gate |
|---|---|---|---|
| Authorization | Mint short-lived, consented, patient-scoped service context | Verify issuer, audience, tenant, patient, purpose, expiry and delegated scope | Cross-tenant, revocation, replay and stale-token tests pass |
| Clinical draft workflow | Add feature-flagged adapter and review UI | Return typed draft/abstention with provenance and idempotency | Synthetic request → review → immutable audit succeeds |
| FHIR/ABDM | Publish minimized resource mapping and consent semantics | Validate resources, terminology, timestamps and evidence references | Differential conformance corpus passes |
| Disease intelligence | Render governed findings without duplicating rules | Own versioned disease packs, calculations and CQL | Reference vectors, boundary cases and abstention tests pass |
| AI providers | Stop direct clinical-provider calls in governed workflows | Own routing, safety, model versions and provider telemetry | No unsafe fallback; unavailable providers are explicit |
| Operational ML | Keep no-show, engagement and churn targets separate | Accept manifests with intended-use and promotion status | No operational proxy promoted as a clinical model |
| Imaging | Supply workflow and review context | Own integrity, provenance, adapter limits and abstention | Corrupt, mismatched and unsupported inputs fail closed |
| Audit | Persist operational clinician decision | Persist model/evidence/rule lineage and hash-chain events | Records are cross-linked and tamper-evident |
| Release | Complete infrastructure, security, recovery and compliance gates | Complete safety, evaluation and open-source gates | Joint signed release decision |

### Step 1 — Contract convergence

The first version of the bridge is now implemented in
`packages/contracts/wyshcare-ai-bridge-v1.schema.json`,
`apps/api/app/bridge_contracts.py`, and the isolated executable route
`POST /v1/integration/wyshcare/clinical-draft`. It has synthetic negative tests
and returns a provenance-bound `ABSTAINED` result because the contract carries
evidence references, not clinical payloads. Extend it only through versioned
changes.

The route is idempotent: a repeated `Idempotency-Key` or request identity returns
the same abstention, while reuse with different content returns `409` and does
not create a second audit event. It remains development-only and synthetic-only.
The repeatable emulator lane is `apps/api/scripts/run_wyshcare_emulator_lane.py`.

The contract contains:

- tenant, patient, practitioner, purpose, consent, and delegated-access claims;
- FHIR bundle/evidence references;
- model/rule/terminology versions;
- draft finding schema;
- abstention and unavailable states;
- review action and audit bindings;
- correlation and idempotency keys.

WyshCare must be the authorization and operational-record authority. wysh.AI
must independently verify the signed context and refuse requests outside scope.

### Step 2 — Intelligence gateway integration

The wysh.AI-side adapter is now implemented in
`apps/api/app/wyshcare_adapter.py` and exercised by
`apps/api/scripts/run_wyshcare_emulator_lane.py`. It uses an injected transport
so the synthetic lane cannot silently become an external production client.
The adapter can:

1. request a synthetic clinical draft from wysh.AI;
2. pass only consented, minimized FHIR context;
3. receive typed evidence references, provenance, model telemetry, and review state;
4. persist nothing as a clinical decision until a WyshCare clinician review is
   completed;
5. handle `ABSTAINED`, `UNAVAILABLE`, timeout, stale-version, and policy-denied
   responses explicitly.

The adapter is verified only in the emulator lane and remains feature-flagged
by architecture: no production endpoint, credential or clinical payload path
is enabled. A WyshCare-native adapter still requires a separately authorized
cross-repository implementation.

### Step 3 — Review and audit convergence

Bind the WyshCare review record to:

- wysh.AI workflow ID;
- input/evidence hash;
- model and rule versions;
- reviewer identity and role;
- review version;
- decision timestamp;
- correction history.

Never let a UI-only approval become an approved clinical record.

### Step 4 — ML convergence without target contamination

Keep WyshCare’s current operational models separate:

- no-show prediction;
- engagement/churn;
- scheduling and workflow optimization.

Use wysh.AI’s registry/evaluation contract for both operational and clinical
models, but give each model an explicit intended-use class. Clinical targets
must not be trained from operational proxy labels without a separate protocol.

### Step 5 — FHIR/ABDM and terminology parity

- Map WyshCare FHIR/ABDM resources into wysh.AI’s typed evidence envelope.
- Add differential tests for consent, patient scope, provenance, timestamps,
  terminology, and missing observations.
- Keep restricted data out of third-party model APIs unless a governing data
  agreement explicitly permits it.
- Add replay, revocation, stale-token, and cross-tenant tests to both repos.

### Step 6 — Clinical validation track

Do not start with production integration. First obtain:

- intended-use approval;
- qualified independent reviewers;
- rights-cleared data;
- reference-standard protocol;
- sample-size/statistical analysis plan;
- ethics/privacy/regulatory review;
- monitoring and stop rules.

Only after those exist should the cross-repository clinical validation lane be
opened.

### Step 7 — Release and open-source track

For wysh.AI:

- confirm copyright holder and license;
- produce SBOM and dependency notices;
- separate source-code, dataset, prompt, image, and model-weight rights;
- remove build output, local databases, secrets, and private artifacts;
- publish synthetic fixtures only;
- retain clinical-use and no-production warnings;
- publish reproducible test evidence.

For WyshCare, keep its existing license and review its much larger dependency,
mobile, infrastructure, and provider surface separately. Do not copy WyshCare
source into wysh.AI or vice versa.

## Target end-state ownership

| Responsibility | Owner |
|---|---|
| Patient identity, consent, tenant, practitioner, operational record | WyshCare |
| Clinical evidence normalization and governed model execution | wysh.AI |
| Deterministic CQL/rule evaluation | wysh.AI |
| Clinical draft review persistence in care workflow | WyshCare, bound to wysh.AI provenance |
| Model registry and safety/evaluation evidence | wysh.AI |
| Operational ML | WyshCare, using shared governance contracts |
| Regulatory/ethics approvals | Authorized clinical/research/legal owners |
| Production release | Joint signed release gate |

## Release gates

WyshCare integration should advance only when:

1. contract parity passes;
2. synthetic end-to-end passes;
3. authorization and consent negative tests pass;
4. model/rule provenance is preserved;
5. reviewer approval is persistent and auditable;
6. rollback and feature flags are tested;
7. independent clinical and regulatory gates are satisfied for the intended
   use.

Until then, the correct architecture is two coordinated systems with a narrow,
typed, fail-closed boundary—not a merged codebase.
