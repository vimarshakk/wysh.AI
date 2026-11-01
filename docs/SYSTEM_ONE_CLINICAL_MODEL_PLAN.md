# wysh.AI — System One Clinical Model Plan

## 1. Objective

Transform **wysh.AI** from a preclinical synthetic scaffold into a **multi-lingual, medically approved System One decision model** using **Laya-class parameters** (~421M ModernBERT backbone), trained on openly available clinical data, deployed air-gapped, and cleared for clinical decision support.

**Guiding principle:** The model outputs **only structured primitives** — Choice, Score, Noul — never free text. It is a high-speed routing engine, not a conversational LLM.

---

## 2. Target Model Specification (Laya Norm)

| Parameter | Target |
|---|---|
| Architecture | Bidirectional encoder-only (ModernBERT-class), no decoder / no text generation |
| Parameter count | ~421M (Laya norm) |
| Input | Structured JSON clinical telemetry state + typed questions |
| Output primitives | **Choice** (discrete option + confidence), **Score** (ordinal 0–10), **Noul** (calibrated P(yes) 0–1) |
| Inference latency | <500ms p95 on CPU |
| Multi-lingual | English + Hindi, Telugu, Tamil, Bengali, Marathi, Spanish, Mandarin, Arabic, French |
| Calibration | RLCD (Reinforcement Learning for Calibrated Decisions) |
| Safety | Abstention below confidence threshold (e.g., <0.85) → automatic human handoff |
| Data privacy | Air-gapped; no PHI leaves the Wysh boundary (DPDP/GDPR/HIPAA-aligned) |
| Approval gate | `CLINICALLY_APPROVED` cannot be set by any code path; requires external qualified governance |

---

## 3. Multi-Lingual Strategy

### Language Tiers

| Tier | Languages | Role |
|---|---|---|
| Tier 1 — Global Research / Interop | English | FHIR R4, ICD-10, SNOMED-CT, LOINC, regulatory submissions |
| Tier 2 — High-Volume Care | Hindi, Telugu, Tamil, Bengali, Marathi, Spanish, Mandarin, Arabic, French | Patient intake, EHR capture, regional prescriptions/labs |
| Tier 3 — Future | Additional Indic / African languages | Adapter-based expansion |

### Technical Approach
- **Shared encoder** with **per-language lightweight adapters** (LoRA-style) so core clinical reasoning is language-agnostic while regional medical terminology is handled per language.
- **Unified ontology gateway**: map all language inputs to standard clinical codes (ICD-10, SNOMED-CT, LOINC, RxNorm) before the decision model scores them. Decision space stays language-invariant.
- **Indic OCR/vision pipeline** for handwritten regional prescriptions and lab sheets → structured JSON telemetry → same System One decision model.

---

## 4. Openly Available Training Data

### Structured Tabular / Time-Series (Score & Choice)
| Source | License | Use |
|---|---|---|
| MIMIC-III / MIMIC-IV | PhysioNet credentialed (DUA) | ICU time-series, vitals, labs, outcomes |
| eICU Collaborative Research Database | PhysioNet | External validation |
| PhysioNet Challenges (sepsis, mortality) | Open | Calibration targets for Noul |
| OpenFDA | Open US government | Medication safety, contraindications |
| ClinicalTrials.gov | Open US government | Trial-matching Choice primitive |
| UCI ML Repository (Heart Disease, Diabetes) | Open | Benchmarking, fixtures |

### Clinical QA / Reasoning (Choice)
| Source | License |
|---|---|
| MedQuAD | Open |
| BioASQ | Open |
| Head-QA (Spanish) | Open |
| MultiMedQA / Med-PaLM benchmarks | Open research |
| MedQA / MedMCQA | Open research |

### Terminology & Ontology
| Source | License |
|---|---|
| ICD-10-CM | WHO |
| LOINC | Regenstrief |
| RxNorm | US NLM |
| SNOMED-CT | UMLS Metathesaurus |
| WHO ATC | WHO |

### Multi-lingual Clinical Text
| Source | Languages | License |
|---|---|---|
| Wikipedia medical articles | Multi-lingual | CC-BY-SA |
| WikiHow health | Multi-lingual | CC-BY-NC-SA |
| MoHFW / NHS / CDC portals | EN + regional | Open government |
| IndicTrans2 / AI4Bharat | Indic | Open research |

**Exclusion rule:** No PHI, no real patient identifiers, no restrictive clinical-use licenses without WyshCare legal review.

---

## 5. Training Architecture

### Phase A — Data Engineering
1. Normalize all sources to a common JSON telemetry schema.
2. De-identification pipeline (strip names, MRNs, phones, addresses, re-identifying dates).
3. Tag each record with ISO-639-1 language code.
4. Gateway ontology mapping (ICD-10/SNOMED-CT/RxNorm).
5. Label generation: Choice (triage protocols), Score (SOFA/qSOFA/CHA₂DS₂-VASc), Noul (binary outcomes).

### Phase B — Model Training
1. Base encoder: ~421M ModernBERT-class open checkpoint.
2. Multi-lingual adapter training on parallel clinical text.
3. Three heads on pooled encoder output: Choice (softmax), Score (regression), Noul (sigmoid).
4. RLCD fine-tuning: reward function penalizes overconfidence on wrong answers, rewards calibrated abstention.
5. Calibration: Platt scaling / isotonic regression on held-out validation.

### Phase C — Evaluation & Validation
1. Internal: AUROC/AUPRC/Brier (Noul), accuracy/F1 (Choice), MAE (Score).
2. External: MIMIC-IV, eICU, separate Indian cohort.
3. Subgroup analysis by language, age, sex, comorbidity.
4. Calibration reliability diagrams.
5. Latency benchmarking (p50/p95/p99 on target hardware).

---

## 6. Medical Approval & Regulatory Pathway

wysh.AI is treated as **Software as a Medical Device (SaMD)**.

| Jurisdiction | Pathway | Key Requirements |
|---|---|---|
| India (CDSCO) | Medical Device Rules 2017 | Clinical evaluation report, performance validation, DPDP compliance |
| USA (FDA) | De Novo / 510(k) | SaMD validation, cybersecurity |
| EU (MDR) | Class IIa–III | Clinical evaluation, ISO 13485 QMS |

### Required artifacts
- Intended Use Statement (decision support only, not autonomous diagnosis)
- Risk Management File (ISO 14971)
- Clinical Evaluation Plan & Report
- Software Validation (IEC 62304)
- QMS (ISO 13485)
- Data Protection Impact Assessment (DPDP/GDPR)

---

## 7. Safety & Calibration (RLCD)

| Mechanism | Implementation |
|---|---|
| Abstention threshold | Noul confidence < 0.85 → automatic human handoff |
| Choice constraints | Output maps to predefined code-level options; malformed responses impossible |
| Calibration monitoring | Continuous reliability diagrams; drift alerts |
| Human-in-the-loop | `human_review_required = true` always |
| No PHI in input | De-identified telemetry only |
| Explainability | Attention rollout mapped to clinical features |

---

## 8. Implementation Roadmap

### Phase 0 — Foundation (Month 1) — STARTING NOW
- Commit this plan to repo
- Define JSON telemetry schema + ontology mapping layer
- Stand up data ingestion pipeline (MIMIC-IV, OpenFDA, ClinicalTrials.gov)
- Legal review of dataset licenses
- Assign roles: ML engineer, clinical safety lead, regulatory consultant

### Phase 1 — Prototype (Months 2–4)
- Train ~421M encoder on normalized data
- Implement Choice / Score / Noul heads
- Baseline evaluation on held-out MIMIC-IV
- RLCD v1 calibration + abstention logic
- Multi-lingual adapter: Hindi + Spanish

### Phase 2 — Clinical Validation (Months 5–9)
- External validation on eICU + Indian cohort
- Subgroup analysis by language / comorbidity
- Clinical safety reviewer panel (blinded comparison)
- ISO 14971 risk management file draft
- Regulatory strategy meeting (CDSCO / FDA)

### Phase 3 — Regulatory Submission (Months 10–14)
- IEC 62304 software validation
- ISO 13485 QMS implementation
- Clinical Evaluation Report
- Submit to CDSCO / FDA
- Air-gapped deployment package (Docker + ONNX)

### Phase 4 — Launch & Surveillance (Month 15+)
- Limited clinical pilot (decision support, human sign-off)
- Post-market surveillance
- Iterative retraining under governance
- Expand to additional Indic languages via adapters

---

## 9. Success Metrics

| Metric | Target |
|---|---|
| Noul AUROC (held-out) | ≥ 0.90 |
| Choice accuracy (triage) | ≥ 0.85 |
| Score MAE (severity 0–10) | ≤ 1.0 |
| Calibration ECE | ≤ 0.05 |
| Inference p95 latency | ≤ 500ms (CPU) |
| Structural hallucination rate | 0% |
| Human handoff rate | 10–20% of low-confidence cases |
| Regulatory clearance | CDSCO / FDA within 18 months |

---

## 10. Immediate Next Steps (Next 30 Days)

1. Commit this PLAN to `docs/SYSTEM_ONE_CLINICAL_MODEL_PLAN.md`
2. Scaffold data ingestion scripts in `apps/api/scripts/`
3. Define JSON telemetry schema in `packages/contracts/`
4. Set up de-identification + validation gate
5. Engage clinical safety advisor + regulatory consultant
6. Benchmark current System One router latency on target hardware
