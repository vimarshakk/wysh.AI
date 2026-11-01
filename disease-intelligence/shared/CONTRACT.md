# Disease Intelligence contract

Every WDI-20 pack follows:

`DiseaseDefinition → DataRequirements → MonitoringPlan → DescriptiveTrend → ClinicalReview → AuthorizedCareAction → OutcomeEvaluation`

The current runtime implements only the first four stages for synthetic data. It produces descriptive trends and missing-data visibility; it does not diagnose, prescribe, triage, assign risk, or execute care actions. Clinical rules, alerts, prescriptions, referrals, and pharmacy actions require separate validated implementations and human authorization.

Patient, clinician, pharmacy, and researcher experiences consume the same versioned disease definition and evidence references. Training use is not implied by care use: patient-specific records remain outside training datasets unless separately consented, de-identified, licensed, and approved.
