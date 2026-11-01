# ISO 13485:2016 Quality Management System — wysh.AI System One

Document ID: QMS-ISO-13485-WYSH-AI-v1.0
Version: 1.0
Status: Draft for regulatory submission
Standard: ISO 13485:2016 — Quality management systems for medical devices

## 1. Quality Management System Overview

### 1.1 Quality Management Policy

**Quality Policy Statement:**
wysh.AI is committed to providing a safe, effective, and reliable Software as a Medical Device (SaMD) for clinical decision support. The system is designed with safety as the primary consideration, featuring deny-by-default operation, synthetic-only data processing, and mandatory human review for all outputs.

**Top Management Commitment:**
- Quality is the primary objective of the organization
- Resources are allocated to maintain and improve the QMS
- Regular management reviews are conducted to ensure continued suitability, adequacy, and effectiveness of the QMS

### 1.2 Quality Management System Elements

| Element | Requirement | Implementation | Status |
|---|---|---|---|
| Document control | Document versioning, approval, change control | Git with signed commits, tagged releases | Implemented |
| Document control | Records retention | 10-year retention policy | Implemented |
| Corrective action | Non-conformance reporting, root cause analysis | Reviewer panel incident logs | Implemented |
| Preventive action | Risk-based prevention | Periodic risk re-evaluation | Implemented |
| Internal audit | Periodic quality system audit | Annual internal audit | Planned |
| Management review | Quarterly review of quality metrics | Dashboard of ECE, handoff rate, drift | Implemented |

## 2. Document Control

### 2.1 Document Control Procedures

| Procedure | Description | Implementation |
|---|---|---|
| **Document approval** | Review and sign-off by quality management | All documents require reviewer sign-off before release |
| **Document revision** | Version increment on each change | Git with signed commits, version tags |
| **Document retention** | 10-year retention for regulatory documents | Archived in secure storage |
| **Document obsolescence** | Identify and remove obsolete documents | Regular review quarterly |

### 2.2 Records Management

| Record Type | Retention Period | Storage |
|---|---|---|
| Software documentation | 10 years after last device shipment | Secure server |
| Clinical data | 10 years after last patient interaction | Secure server with encryption |
| Risk management | 10 years after device lifecycle end | Secure server |
| Clinical evaluation | 10 years after device lifecycle end | Secure server |

## 3. Corrective and Preventive Action (CAPA)

### 3.1 CAPA Policy

The CAPA process ensures that quality issues are identified, investigated, and resolved in a timely manner.

| Step | Description | Timeline | Responsible |
|---|---|---|---|
| **Non-conformance reporting** | Report quality issues via reviewer panel | Immediate | Clinical safety team |
| **Root cause analysis** | RCA using 5 Whys or fishbone diagram | Within 5 business days | Clinical safety team + QA |
| **Corrective action** | Fix implementation and verification | Within 30 days | DevOps team |
| **Preventive action** | Process improvement to prevent recurrence | Within 30 days | Quality management |
| **Verification** | Testing and verification of fixes | Within 30 days | QA team |
| **Effectiveness check** | Follow-up after 30/90/180 days | 30/90/180 days | Quality management |

### 3.2 CAPA Records

- **Records retention**: 10 years
- **Review**: Quarterly management review
- **Sign-off**: Quality management representative

## 4. Internal Audit

| Activity | Frequency | Description |
|---|---|---|
| **Internal audit** | Annual | Quality management system audit |
| **Audit planning** | Annual | Define audit scope and objectives |
| **Audit execution** | As scheduled | Execute audit per plan |
| **Audit reporting** | Immediately after audit | Document findings and corrective actions |
| **Management review** | Incorporate audit results | Include in management review meeting |

### 4.1 Internal Audit Plan

| Element | Description |
|---|---|
| **Audit scope** | Quality management system, risk management, clinical evaluation |
| **Audit frequency** | Annual |
| **Audit team** | Quality management representative, clinical safety team |
| **Audit objectives** | Verify compliance with ISO 13485, ISO 14971, and this QMS |

### 4.2 Internal Audit Report Template

| Section | Content |
|---|---|
| Audit scope and objectives | Scope of audit, objectives, criteria |
| Findings and observations | Non-conformances, observations, opportunities for improvement |
| Corrective action requirements | Required corrective actions, owners, due dates |
| Follow-up requirements | Verification of corrective action effectiveness |
| Management sign-off | Quality management representative signature |

## 5. Clinical Evaluation

### 5.1 Clinical Evaluation Plan

| Element | Description |
|---|---|
| **Clinical question** | Does the System One decision model provide accurate triage/routing for [indication]? |
| **Target population** | Demographic characteristics, age range, comorbidity profile |
| **Clinical evidence** | External clinical validation data, subgroup performance, clinical safety reviewer panel results |
| **Clinical success criteria** | AUROC ≥ 0.90, ECE ≤ 0.05, abstention rate 10–20%, no structural hallucinations |
| **Data sources** | MIMIC-IV, Indian clinical cohort, clinical safety reviewer panel, literature review |

### 5.2 Clinical Evaluation Report Outline

| Section | Content |
|---|---|
| 1. Introduction | Intended use, indications for use, target population |
| 2. Literature search | Database search strategy, databases searched, search dates |
| 3. Literature selection | Inclusion/exclusion criteria, number of studies selected |
| 4. Clinical evidence | Summary of each study, study design, results |
| 5. Clinical benefit | Assessment of clinical benefit, benefit-risk analysis |
| 5. Clinical safety | Adverse events, adverse event rates, safety signals |
| 6. Benefit-risk analysis | Benefit-risk analysis, clinical relevance |
| 7. Conclusion | Summary of clinical benefits, areas for future research |

### 5.3 Clinical Evaluation Process

| Step | Activity | Timeline |
|---|---|---|
| **1. Literature search** | Database search, study selection | Month 1–2 |
| **2. Literature selection** | Eligibility assessment, quality assessment | Month 3 |
| **3. Data extraction** | Data extraction, quality assessment | Month 4 |
| **4. Clinical evidence synthesis** | Meta-analysis, subgroup analysis | Month 5–6 |
| **5. Clinical benefit assessment** | Benefit-risk analysis, clinical relevance | Month 7 |
| **6. Clinical safety assessment** | Adverse event analysis, safety signals | Month 7–8 |
| **7. Clinical evaluation report** | Compilation and writing | Month 9 |

## 6. Quality Management Metrics

| Metric | Target | Measurement Source |
|---|---|---|
| ECE (Expected Calibration Error) | ≤ 0.05 | Computed from validation data |
| Abstention rate | 10–20% | Computed from validation data |
| Human handoff rate | Configurable | Computed from reviewer panel |
| Non-conformance rate | < 1% per quarter | Incident reports / total reviews |
| Deviation rate | < 1% per quarter | SRS deviations / total requirements |

### 6.1 Quality Metrics Dashboard

| Metric | Target | Current Value |
|---|---|---|
| ECE | ≤ 0.05 | To be computed |
| Abstention rate | 10–20% | To be computed |
| Human handoff rate | Configurable | To be computed |
| Non-conformance rate | < 1% per quarter | To be monitored |
| Deviation rate | < 1% per quarter | To be monitored |

The quality dashboard is updated quarterly and presented to management during the management review meeting.

## 7. Management Review

### 7.1 Management Review Process

Quarterly management review includes:

- Results of internal audits
- Results of external audits
- Feedback and complaints from users and patients
- Trend analysis of quality metrics
- Assessment of the continuing need for the medical device
- Evaluation of the effectiveness of risk controls
- Decisions and actions related to the medical device

### 7.2 Management Review Inputs

| Input | Description |
|---|---|
| Internal audit results | Findings and corrective actions from internal audits |
| External audit results | Findings from external audits |
| User/patient feedback | Complaints, suggestions, adverse event reports |
| Quality metrics trends | ECE, abstention rate, handoff rate trends |
| Device need assessment | Continuing need for the medical device |
| Risk control evaluation | Effectiveness of implemented risk controls |
| Device decisions | Actions related to the medical device |

### 7.3 Management Review Meeting

| Element | Description |
|---|---|
| **Agenda** | Review of quality metrics, risk management, and clinical evidence |
| **Attendees** | Quality management representative, clinical safety team, regulatory affairs |
| **Duration** | 2 hours |
| **Frequency** | Quarterly |
| **Outputs** | Management review report, action items, follow-up dates |

### 7.4 Management Review Meeting Minutes Template

- Date and duration of the meeting
- Attendees and their roles
- Summary of discussion points
- Decisions made
- Action items and follow-up dates

### 7.5 Management Review Reporting

Management review results are communicated to:

- Senior management
- Quality management representative
- Regulatory affairs (as required)
- Notified body (if applicable)

## 8. Regulatory Compliance

### 8.1 FDA SaMD Classification

| Classification | Criteria |
|---|---|
| Risk Class | Class II (US) |
| SaMD Type | Decision support, not autonomous |
| Indications | Diabetes, hypertension, chronic kidney disease |
| Predicate Devices | None (De Novo pathway) |

### 8.2 FDA Submission Strategy

| Submission Type | Timeline | Requirements |
|---|---|---|
| De Novo | 12–18 months | Clinical data, risk management, calibration |
| 510(k) | 6–12 months | Predicate device, substantial equivalence |
| CDSCO India | 6–9 months | CDSCO Form 40, risk management |

### 8.3 CE Marking (MDR)

| Element | Requirement |
|---|---|
| Classification | Class IIa |
| Notified Body | Required for conformity assessment |
| Technical File | Includes IEC 62304, ISO 14971, and CER |
| Declaration of Conformity | Signed by manufacturer, submitted to national authorities |

## 9. Risk Management Integration

The risk management process (ISO 14971) is integrated with the QMS:

- **Risk management review** is part of the management review process
- **Hazard identification** uses the same data sources as the quality management system
- **Risk controls** are verified through the validation process
- **Residual risk** is monitored throughout the lifecycle

## 10. Appendices

### A. Quality Management Metrics Table

| Metric | Target | Current Value | Source |
|---|---|---|---|
| ECE | ≤ 0.05 | To be computed | Validation data |
| Abstention rate | 10–20% | To be computed | Reviewer panel |
| Human handoff rate | Configurable | To be computed | Reviewer panel |
| Non-conformance rate | < 1% per quarter | To be computed | Incident reports |
| Deviation rate | < 1% per quarter | To be computed | SRS deviations |

### B. Internal Audit Plan

| Element | Description |
|---|---|
| Audit scope | QMS, risk management, clinical evaluation |
| Audit frequency | Annual |
| Audit team | Quality management representative, clinical safety team |
| Audit objectives | Verify compliance with ISO 13485, ISO 14971, QMS |

### C. Management Review Meeting Template

- Date and duration of the meeting
- Attendees and their roles
- Summary of discussion points
- Decisions made
- Action items and follow-up dates

---
