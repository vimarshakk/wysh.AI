# IEC 62304 Software Development Lifecycle — wysh.AI System One

Document ID: IEC-62304-WYSH-AI-v1.0
Version: 1.0
Status: Draft for regulatory submission
Standard: IEC 62304:2006 / Amd 1:2015 — Medical device software lifecycle

## 1. Software Lifecycle Process

### 1.1 Software States

| State | Description | Transition Rule |
|---|---|---|
| **Planned** | Intended for use, not yet loaded | Planned → Planned (new version) |
| **Loaded** | Loaded into execution memory | Load → Execute |
| **Execute** | Execute the software | Execute → Load (restart) |
| **Suspend** | Suspend execution | Execute → Suspend |
| **Abort** | Abort the execution | Execute → Abort |

### 1.2 Software Development Process Model

| Process | Description | Standard Reference |
|---|---|---|
| **Defining** | Define software requirements | IEC 62304, Clause 5 |
| **Realizing** | Develop and verify the software | IEC 62304, Clause 6 |
| **Verifying** | Verify software meets requirements | IEC 62304, Clause 7 |
| **Validating** | Validate software meets user needs | IEC 62304, Clause 8 |
| **Maintaining** | Maintain software after deployment | IEC 62304, Clause 9 |

## 2. Software Development Constraints

### 2.1 Planned State Entry Constraint

The software shall only enter the Planned state when:
- All required documentation is complete and approved
- All safety controls are in place and verified
- Regulatory approval is obtained where necessary

### 2.2 Execute State Entry Constraint

The software shall only enter the Execute state when:
- The software has been loaded successfully
- All safety checks have passed
- The software is configured for the intended use

## 3. Software Development Activities

### 3.1 Defining — Software Requirements

#### 3.1.1 Intended Use

The wysh.AI System One decision model provides structured clinical decision support for routine background triage and routing checks. It evaluates structured clinical telemetry and emits structured routing decisions (Choice, Score, Noul) with calibrated confidence.

**NOT intended for:** Autonomous diagnosis, prescribing, treatment recommendations, emergency response, or PHI processing without consent.

#### 3.1.2 User Needs

| User Type | Role | Training Requirement |
|---|---|---|
| Clinician-safety | Reviews model outputs, adjudicates decisions | Medical degree, clinical safety training |
| Clinical-lead | Oversees clinical safety review process | Medical degree, leadership experience |
| Regulatory | Reviews regulatory compliance | Regulatory affairs training |
| Ethics | Reviews ethical considerations | Ethics committee membership |

#### 3.1.3 Operating Constraints

| Constraint | Implementation |
|---|---|
| **Synthetic-only** | De-identification gate rejects PHI; `synthetic: true` required |
| **Deny-by-default** | `clinical_use_authorized = false` unless external governance approves |
| **Human review required** | `human_review_required = true` for all outputs |
| **No PHI** | Context rejects names, MRNs, emails, phones, addresses |
| **No text generation** | Structured primitives only (Choice, Score, Noul) |

#### 3.1.4 Performance Requirements

| Metric | Target | Measurement |
|---|---|---|
| Noul AUROC | ≥ 0.90 | Held-out validation data |
| Choice accuracy | ≥ 85% | Triage task evaluation |
| Score MAE | ≤ 1.0 | 0–10 severity scale |
| Calibration (ECE) | ≤ 0.05 | Reliability diagrams |
| Inference latency | ≤ 500ms p95 | CPU benchmark |

#### 3.1.5 Software Safety Classification

| Classification | Criteria |
|---|---|
| Risk Class | Class II (US) / Class B (EU) |
| SaMD Type | Decision support, not autonomous |
| Clinical Use | Decision support only |
| Safety Classification | NEGLIGIBLE → MINOR → SERIOUS → CRITICAL |

### 3.2 Realizing — Software Components

| SCI Type | Description | Files |
|---|---|---|
| Software Requirements | Intended use, operating environment, safety constraints | `docs/regulatory/` |
| Software Architecture | High-level design, component diagram, data flow | `apps/api/app/` |
| Software Design | Detailed design of modules, algorithms, interfaces | `apps/api/app/system_one/` |
| Unit Tests | Test cases for individual functions/modules | `apps/api/tests/` |
| Integration Tests | End-to-end validation, external validation | `apps/api/tests/` |
| Maintenance | Patches, updates, retirement procedures | `docs/` |

### 3.3 Software Architecture

#### 3.3.1 Components

| Component | Description | Location |
|---|---|---|
| System One Encoder | ModernBERT-class bidirectional encoder (~421M params target) | `apps/api/app/system_one/encoder.py` |
| Decision Heads | Choice, Score, Noul output heads | `apps/api/app/system_one/decision_heads.py` |
| RLCD Calibration | Reinforcement Learning for Calibrated Decisions | `apps/api/app/system_one/rlcd.py` |
| Training Pipeline | Orchestration of training pipeline | `apps/api/app/system_one/training_pipeline.py` |
| Validation Engine | External validation, metrics, subgroup analysis | `apps/api/app/system_one/validation_engine.py` |
| Reviewer Panel | Clinical safety reviewer interface | `apps/api/app/system_one/reviewer_panel.py` |
| Risk Register | ISO 14971 risk management | `apps/api/app/system_one/risk_register.py` |

#### 3.3.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    System One Decision Router               │
│  ┌─────────────┬─────────────────┬───────────────────────┐ │
│  │  Feature    │  Routing Engine │  Decision Model       │ │
│  │  Extractor  │                 │  (logistic /          │ │
│  │             │                 │  threshold rules)     │ │
│  └─────────────┴─────────────────┴───────────────────────┘ │
│  ┌─────────────┬─────────────────┬───────────────────────┐ │
│  │   Choice    │    Score        │      Noul             │ │
│  │   Head      │    Head         │      Head             │ │
│  └─────────────┴─────────────────┴───────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
        ▲                    ▲                    ▲
 Structured          Model         Structured
 clinical facts      selection     routing decision
 (typed evidence)    by indication (action, confidence,
                     abstention)
```

### 3.4 Verifying — Software Verification

#### 3.4.1 Unit Verification

Each unit of software is verified against its requirements through unit tests.

| Test Module | Description | Coverage |
|---|---|---|
| `test_feature_extractor.py` | Deterministic feature extraction | FeatureExtractor |
| `test_decision_model.py` | Decision model inference | SystemOneDecisionModel |
| `test_routing_engine.py` | Routing engine selection | RoutingEngine |
| `test_system_one_router.py` | End-to-end routing | SystemOneRouter |
| `test_encoder.py` | System One encoder | SystemOneEncoder |
| `test_decision_heads.py` | Choice/Score/Noul heads | DecisionHeads |
| `test_rlcd.py` | RLCD calibration | SystemOneRLCD |
| `test_training_pipeline.py` | Training pipeline | TrainingPipeline |
| `test_validation_engine.py` | Validation engine | ValidationEngine |
| `test_reviewer_panel.py` | Reviewer panel | ReviewerPanel |
| `test_risk_register.py` | Risk register | RiskRegister |
| `test_telemetry_schema.py` | Telemetry schema | Contract validation |

**Test coverage target:** ≥ 80% line coverage

**Current test count:** 281+ passing tests

#### 3.4.2 Integration Verification

The software is verified as an integrated system through end-to-end routing tests that exercise the complete pipeline from feature extraction to routing decision.

### 3.5 Validating — Software Validation

#### 3.5.1 Validation Plan

| Element | Description |
|---|---|
| Intended use | Decision support for clinical triage and routing |
| Target population | Synthetic adult patients with chronic conditions |
| Clinical validation data | MIMIC-IV + Indian clinical cohort |
| Acceptance criteria | AUROC ≥ 0.90, ECE ≤ 0.05, abstention rate 10–20% |

#### 3.5.2 Validation Evidence

| Evidence | Source | Status |
|---|---|---|
| External validation | MIMIC-IV held-out data | Pending dataset |
| Subgroup analysis | Language/comorbidity subgroups | Pending dataset |
| Clinical safety review | Reviewer panel | Pending panel |
| Risk management | ISO 14971 risk register | Implemented |

### 3.6 Maintaining — Software Maintenance

#### 3.6.1 Maintenance Activities

| Activity | Frequency | Trigger |
|---|---|---|
| Corrective maintenance | As needed | Critical bug fix, security update |
| Adaptive maintenance | Quarterly | Environment changes |
| Perfective maintenance | Quarterly | Performance improvement, new features |
| Preventive maintenance | Quarterly | Prevent future issues |

#### 3.6.2 Change Control

All software changes shall:
- Be documented with version changes
- Be verified against requirements
- Be validated against user needs
- Be reviewed by safety reviewer
- Be approved by quality management

### 4. Software Risk Management (ISO 14971 Integration)

| Risk Category | Risk Level | Control Measure | Residual Risk |
|---|---|---|---|
| Overconfident wrong triage | CRITICAL | Human handoff on low confidence | LOW |
| Missing data inference | SERIOUS | Abstention on missing metrics | MINOR |
| PHI leakage | CRITICAL | De-identification gate | NEGLIGIBLE |
| Language bias | MODERATE | Multi-lingual adapters | MINOR |
| Clinical misuse | CRITICAL | Deny-by-default + human review | MINOR |

### 5. Appendices

#### A. Revision History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-11-01 | System One Team | Initial release |

#### B. References

- IEC 62304:2006 / Amd 1:2015 — Medical device software lifecycle
- ISO 14971:2019 — Medical device risk management
- ISO 13485:2016 — Quality management systems for medical devices

---
