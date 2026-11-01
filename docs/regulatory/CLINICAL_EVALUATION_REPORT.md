# Clinical Evaluation Report — wysh.AI System One Decision Model

Document ID: CER-SystemOne-v1.0
Version: 1.0
Status: Draft for regulatory submission
Device: wysh.AI WMI-1 System One Decision Model
Device Classification: Class II (US) / Class B (EU) SaMD

## 1. Document Control

| Field | Value |
|---|---|
| **Document ID** | CER-SystemOne-v1.0 |
| **Document Title** | Clinical Evaluation Report — wysh.AI System One Decision Model |
| **Version** | 1.0 |
| **Date** | November 2026 |
| **Author** | Clinical Safety Team |
| **Approver** | Quality Management Representative |
| **Status** | Draft for Regulatory Submission |
| **Regulatory Pathway** | CDSCO (India), FDA De Novo/510(k) (US), CE MDR (EU) |

## 2. Revision History

| Version | Date | Author | Description |
|---|---|---|---|
| 0.1 | 2026-10-01 | Clinical Safety Team | Initial draft |
| 0.5 | 2026-10-15 | Clinical Safety Team | Added subgroup analysis |
| 1.0 | 2026-11-01 | Clinical Safety Team | Final draft for submission |

## 3. Approval Signatures

| Role | Name | Signature | Date |
|---|---|---|---|
| Clinical Safety Lead | [MD Name] | [Digital Signature] | [Date] |
| Quality Management Representative | [Name] | [Digital Signature] | [Date] |
| Regulatory Affairs | [Name] | [Digital Signature] | [Date] |

## 4. Table of Contents

1. Document Control
2. Revision History
3. Approval Signatures
4. Table of Contents
5. Introduction
6. Device Description
7. Intended Use and Indications for Use
8. Clinical Evaluation Methodology
9. Clinical Evidence
10. Clinical Benefit Analysis
11. Clinical Safety Analysis
12. Benefit-Risk Analysis
13. Conclusion
14. Appendices

---

## 5. Introduction

### 5.1 Purpose

The purpose of this Clinical Evaluation Report (CER) is to demonstrate that the wysh.AI System One decision model is safe and effective for its intended use as a clinical decision support tool. This CER is prepared in accordance with ISO 14971:2019, ISO 13485:2016, IEC 62304:2006/Amd1:2015, and applicable regulatory guidance from CDSCO, FDA, and EU MDR.

### 5.2 Scope

This CER covers the wysh.AI System One decision model software component, including:
- System One encoder (ModernBERT-class, ~421M parameter target)
- Decision heads (Choice, Score, Noul primitives)
- RLCD calibration engine
- Training pipeline with synthetic-only data governance
- Validation engine for external validation and subgroup analysis
- Clinical safety reviewer panel
- ISO 14971 risk register

### 5.3 Definitions

| Term | Definition |
|---|---|
| SaMD | Software as a Medical Device |
| System One | Fast deterministic decision model architecture |
| System Two | Conversational LLM architecture (not used on hot path) |
| Noul | Calibrated binary probability P(yes) output (0–1) |
| Choice | Discrete option selection with confidence |
| Score | Ordinal clinical severity score (0–10) |
| RLCD | Reinforcement Learning for Calibrated Decisions |
| Synthetic-only | No real patient data without separate consent/de-identification |
| Deny-by-default | Clinical use not authorized by default |
| Abstention | Model declines to make a prediction below confidence threshold |
| Human handoff | Automatic transfer to human reviewer when model abstains |

---

## 6. Device Description

### 6.1 Device Identification

| Item | Description |
|---|---|
| **Device Name** | wysh.AI WMI-1 System One Decision Model |
| **Model Number** | WMI-1-v1.0 |
| **Software Version** | 1.0 |
| **Device Classification** | Class II (US) / Class B (EU) SaMD |
| **Regulatory Pathway** | CDSCO Form 40 (India), FDA De Novo (US), CE MDR Annex III (EU) |

### 6.2 Device Components

| Component | Description | Safety Classification |
|---|---|---|
| System One Encoder | ModernBERT-class bidirectional encoder (~421M parameters) | NEGLIGIBLE |
| Decision Heads | Choice, Score, Noul output heads | MINOR |
| RLCD Calibration | Temperature scaling, confidence threshold abstention | MINOR |
| Training Pipeline | Governed synthetic dataset + de-identification gate | NEGLIGIBLE |
| Validation Engine | External validation, metrics, subgroup analysis | NEGLIGIBLE |
| Reviewer Panel | Clinical safety reviewer interface | MINOR |
| Risk Register | ISO 14971 hazard tracking | NEGLIGIBLE |

### 6.3 Device Operation

The wysh.AI System One decision model operates as follows:

1. **Input**: Structured clinical telemetry JSON (clinical-telemetry-v1 schema) with typed observations, conditions, medications, encounters, and typed questions
2. **Encoding**: Features extracted deterministically, encoded via ModernBERT-class encoder with per-language adapters
3. **Decision**: Choice/Score/Noul heads output structured primitives with confidence scores
4. **Calibration**: RLCD temperature scaling applied; abstention triggered below 0.85 confidence
5. **Output**: Structured decision (action, confidence, abstention reason, model path)
6. **Review**: All outputs flagged `human_review_required = true`; `clinical_use_authorized = false` until CLINICALLY_APPROVED via external governance

### 6.4 Safety Constraints

| Constraint | Description |
|---|---|
| Synthetic-only | No PHI or real patient data accepted without separate consent |
| Deny-by-default | `clinical_use_authorized = false` unless external governance approves |
| Human review required | `human_review_required = true` for all outputs |
| No text generation | No conversational output; structured primitives only |
| Fail closed | Model abstains on missing evidence, unknown models, or invalid inputs |

---

## 7. Intended Use and Indications for Use

### 7.1 Intended Use

The wysh.AI System One decision model is intended to provide structured clinical decision support for routine background triage and routing checks in preclinical research settings. It evaluates structured clinical telemetry and emits structured routing decisions (Choice, Score, Noul) with calibrated confidence, enabling fast, deterministic clinical routing without conversational text generation.

### 7.2 Indications for Use

| Indication | Description | Target Population |
|---|---|---|
| Diabetes review | Glycemic control assessment, triage routing | Synthetic adult patients with diabetes-monitoring observations |
| Hypertension review | Blood pressure control assessment, triage routing | Synthetic adult patients with blood-pressure observations |
| Chronic kidney disease review | Kidney function assessment, triage routing | Synthetic adult patients with kidney-related observations |

### 7.3 Contraindications

| Contraindication | Description |
|---|---|
| Autonomous diagnosis | Not intended for autonomous clinical diagnosis |
| Prescribing | Not intended for medication prescription |
| Treatment recommendations | Not intended for treatment planning |
| Emergency response | Not intended for emergency medical decision-making |
| PHI processing | Not intended for processing protected health information without consent |

### 7.4 User Profile

| User Type | Role | Training Requirement |
|---|---|---|
| Clinician-safety | Reviews model outputs, adjudicates decisions | Medical degree, clinical safety training |
| Clinical-lead | Oversees clinical safety review process | Medical degree, leadership experience |
| Regulatory | Reviews regulatory compliance | Regulatory affairs training |
| Ethics | Reviews ethical considerations | Ethics committee membership |

---

## 8. Clinical Evaluation Methodology

### 8.1 Evaluation Approach

The clinical evaluation follows a two-pronged approach:

1. **External validation**: Testing on held-out de-identified clinical data (MIMIC-IV + Indian clinical cohort)
2. **Clinical safety review**: Structured review by qualified clinical safety reviewers

### 8.2 Data Sources

| Data Source | Type | License | Use |
|---|---|---|---|
| MIMIC-IV | ICU time-series | PhysioNet credentialed | External validation |
| OpenFDA | Drug labels, adverse events | Open US government | Medication safety scoring |
| ClinicalTrials.gov | Trial protocols | Open US government | Trial-matching Choice primitive |
| Indian clinical cohort | De-identified clinical records | TBD | Subgroup analysis by language |

### 8.3 Evaluation Metrics

| Metric | Target | Definition |
|---|---|---|
| Noul AUROC | ≥ 0.90 | Area under ROC curve for binary outcome prediction |
| Noul AUPRC | ≥ 0.85 | Area under precision-recall curve |
| Noul Brier score | ≤ 0.15 | Mean squared error of probability predictions |
| Noul ECE | ≤ 0.05 | Expected Calibration Error |
| Choice accuracy | ≥ 85% | Accuracy of discrete option selection |
| Abstention rate | 10–20% | Rate of model abstention below confidence threshold |
| Human handoff rate | Configurable | Rate of automatic human review triggers |

### 8.4 Subgroup Analysis

| Dimension | Subgroups |
|---|---|
| Language | en, hi, te, ta, bn, mr, es, zh, ar, fr |
| Age band | 18–44, 45–64, 65+ |
| Sex | M, F |
| Comorbidity count | 0, 1, 2, 3+ |

### 8.5 Clinical Safety Review

The clinical safety reviewer panel performs structured review of model outputs:

- **Reviewer roles**: clinician-safety, clinical-lead, regulatory, ethics
- **Review decisions**: APPROVE / REJECT / ABSTAIN / REQUEST_REVISION
- **Human handoff**: Automatic for ABSTAIN and REQUEST_REVISION decisions
- **Conflict of interest**: Declared and documented for each reviewer

---

## 9. Clinical Evidence

### 9.1 Validation Results Summary

| Metric | Result | Status |
|---|---|---|
| Noul AUROC | Pending external validation | In progress |
| Noul AUPRC | Pending external validation | In progress |
| Noul Brier score | Pending external validation | In progress |
| Noul ECE | Pending external validation | In progress |
| Choice accuracy | Pending external validation | In progress |
| Abstention rate | Pending external validation | In progress |

### 9.2 Subgroup Analysis Results

| Dimension | Subgroup | AUROC | Choice Accuracy | Abstention Rate |
|---|---|---|---|---|
| Language | en | Pending | Pending | Pending |
| Language | hi | Pending | Pending | Pending |
| Language | te | Pending | Pending | Pending |
| Age band | 18–44 | Pending | Pending | Pending |
| Age band | 45–64 | Pending | Pending | Pending |
| Age band | 65+ | Pending | Pending | Pending |
| Sex | M | Pending | Pending | Pending |
| Sex | F | Pending | Pending | Pending |

*Note: Results pending external validation dataset availability.*

### 9.3 Safety Review Results

| Metric | Result | Status |
|---|---|---|
| Reviewer agreement rate | Pending | Pending clinical safety panel |
| Human handoff rate | Pending | Pending validation data |
| Adverse events | None reported | Preclinical only |
| Safety signals | None identified | Preclinical only |

---

## 10. Clinical Benefit Analysis

### 10.1 Clinical Benefit

| Benefit | Description | Evidence |
|---|---|---|
| Fast triage | Sub-second structured routing decisions | Architecture design |
| Zero structural hallucination | No text generation; structured primitives only | System architecture |
| Calibrated confidence | RLCD temperature scaling | RLCD module |
| Automatic human handoff | Abstention triggers clinician review | Safety design |
| Multi-lingual support | 10 languages with shared encoder | Encoder module |

### 10.2 Clinical Benefit Quantification

| Benefit | Quantification | Target |
|---|---|---|
| Inference latency | ≤ 500ms p95 on CPU | Performance requirement |
| Triage accuracy | ≥ 85% | Performance requirement |
| Calibration (ECE) | ≤ 0.05 | Performance requirement |
| Human review rate | 100% | Safety requirement |

---

## 11. Clinical Safety Analysis

### 11.1 Safety Constraints

| Constraint | Implementation |
|---|---|
| Synthetic-only | De-identification gate rejects PHI |
| Deny-by-default | `clinical_use_authorized = false` unless external governance |
| Human review required | `human_review_required = true` for all outputs |
| Fail closed | Model abstains on missing evidence or invalid inputs |
| No PHI | Context rejects names, MRNs, emails, phones |

### 11.2 Risk Management (ISO 14971)

| Risk Category | Risk Level | Control Measure | Residual Risk |
|---|---|---|---|
| Overconfident wrong triage | CRITICAL | Human handoff on low confidence | LOW |
| Missing data inference | SERIOUS | Abstention on missing metrics | MINOR |
| PHI leakage | CRITICAL | De-identification gate | NEGLIGIBLE |
| Language bias | MODERATE | Multi-lingual adapters | MINOR |
| Clinical misuse | CRITICAL | Deny-by-default + human review | MINOR |

### 11.3 Adverse Events

| Adverse Event | Frequency | Severity | Mitigation |
|---|---|---|---|
| None reported | N/A | N/A | Preclinical only |

*Note: No adverse events reported as device is preclinical and synthetic-only.*

### 11.4 Safety Signals

| Safety Signal | Description | Status |
|---|---|---|
| None identified | N/A | Preclinical only |

---

## 12. Benefit-Risk Analysis

### 12.1 Benefit-Risk Overview

The wysh.AI System One decision model offers structured, fast, calibrated clinical decision support with automatic human handoff for low-confidence cases. The device is intended for decision support only — not autonomous diagnosis or treatment.

### 12.2 Benefit-Risk Comparison

| Aspect | Benefit | Risk | Net Assessment |
|---|---|---|---|
| Clinical accuracy | ≥ 85% triage accuracy | Wrong triage if overconfident | Positive (human handoff mitigates) |
| Speed | ≤ 500ms p95 inference | None significant | Positive |
| Calibration | ECE ≤ 0.05 | None significant | Positive |
| Safety | Automatic human handoff | None significant | Positive |
| Multi-lingual | 10 languages supported | Language bias possible | Positive (adapters mitigate) |

### 12.3 Benefit-Risk Conclusion

The benefits of the wysh.AI System One decision model — fast, calibrated, structured clinical decision support with automatic human handoff — outweigh the risks, which are mitigated by deny-by-default operation, synthetic-only processing, and mandatory human review.

---

## 13. Conclusion

### 13.1 Summary

The wysh.AI System One decision model is a preclinical, synthetic-only clinical decision support system that:
- Provides structured routing decisions (Choice, Score, Noul) with calibrated confidence
- Operates with deny-by-default and deny-by-default clinical use authorization
- Requires human review for all outputs
- Supports 10 languages with shared encoder architecture
- Maintains ISO 14971 risk management and ISO 13485 QMS compliance

### 13.2 Areas for Future Research

| Area | Description | Priority |
|---|---|---|
| External validation | Complete validation on MIMIC-IV + Indian clinical cohort | High |
| Calibration study | Preregistered RLCD calibration validation | High |
| Subgroup expansion | Additional Indic languages, African languages | Medium |
| Long-term safety | Post-market surveillance | Medium |
| Regulatory submission | CDSCO Form 40, FDA De Novo/510(k), CE MDR | High |

### 13.3 Regulatory Status

| Regulatory Body | Pathway | Status |
|---|---|---|
| CDSCO (India) | Form 40 | Preparation |
| FDA (US) | De Novo / 510(k) | Preparation |
| CE MDR (EU) | Class IIa Annex III | Preparation |

---

## 14. Appendices

### A. Glossary

| Term | Definition |
|---|---|
| System One | Fast deterministic decision model architecture |
| System Two | Conversational LLM architecture (not used on hot path) |
| Noul | Calibrated binary probability (0–1) |
| Choice | Discrete option selection |
| Score | Ordinal clinical severity score (0–10) |
| RLCD | Reinforcement Learning for Calibrated Decisions |
| ECE | Expected Calibration Error |
| SaMD | Software as a Medical Device |

### B. References

1. IEC 62304:2006 / Amd 1:2015 — Medical device software lifecycle
2. ISO 14971:2019 — Medical device risk management
3. ISO 13485:2016 — Quality management systems for medical devices
4. FDA SaMD Guidance — Decisions support software
5. ISO 14971:2019 — Risk management

---
