export type Measurement = {
  measurement_id: string;
  metric: string;
  value: number;
  unit: string;
  observed_at: string;
  source_type: "observation" | "laboratory" | "medication" | "questionnaire" | "encounter";
};

export type PatientSummary = {
  case_id: string;
  disease_id: string;
  measurement_count: number;
  expected_engineering_status: string;
  synthetic: true;
};

export type PatientCase = PatientSummary & { measurements: Measurement[] };
export type Finding = { code: string; severity: "INFO" | "REVIEW" | "ABSTAIN"; message: string; evidence_refs: string[] };
export type Assessment = {
  assessment_id: string;
  disease_id: string;
  pack_version: string;
  findings: Finding[];
  missing_metrics: string[];
  follow_up_status: "REVIEW_REQUIRED" | "NO_GAP_DETECTED" | "ABSTAINED";
  care_plan: { draft_only: true; clinician_approval_required: true; proposed_actions: string[]; blocked_actions: string[] } | null;
  abstained: boolean;
  rationale: string;
  provenance: { input_hash: string; engine_version: string; evidence_refs: string[]; synthetic_only: true };
  clinical_use_authorized: false;
  human_review_required: true;
};
export type MonitoringResponse = { disease_id: string; workflow_version: string; trends: Array<{ metric: string; direction: string; points: number; first_value: number | null; latest_value: number | null; unit: string | null; evidence_refs: string[] }>; missing_domains: string[]; interpretation_status: "DESCRIPTIVE_ONLY"; rationale: string; input_hash: string; human_review_required: true; clinical_use_authorized: false };

export type EvaluationStatus = {
  wdi_program_status: string;
  local_api_tests: string;
  wdi20_e2e: string;
  phase1_evaluation: string;
  candidate_resources: number;
  clinical_validation: string;
  external_connectivity: string;
};
export type RuleGovernanceStatus = { rule_id: string; rule_version: string; evidence_id: string; registry_approval_status: "ENGINEERING_ONLY" | "CLINICALLY_REVIEWED"; lifecycle_available: boolean; clinical_use_authorized: false; clinical_approval_claimed: false; synthetic_only: true };
export type ClinicalReview = { review_id: string; tenant_id: string; patient_id: string; disease_id: string; assessment_id: string; assessment_input_hash: string; state: string; version: number; created_at: string; updated_at: string; created_by: string; latest_action: string; events: Array<{ event_id: string; review_id: string; version: number; action: string; actor_subject: string; actor_role: string; note: string | null; occurred_at: string }> };
export type VerifiedCalculation = { calculation_id: string; disease_id: string; calculations: Array<{ code: string; status: "CALCULATED" | "ABSTAINED"; value: number | null; unit: string | null; formula: string; reference_id: string; evidence_refs: string[]; limitation: string }>; abstained: boolean; rationale: string; provenance: { input_hash: string; calculation_version: string; synthetic_only: true }; clinical_use_authorized: false; human_review_required: true };
export type DiseaseSpecific = { assessment_id: string; disease_id: string; pack_version: string; status: "DATA_QUALITY_ONLY" | "ABSTAINED"; findings: Array<{ code: string; severity: string; message: string; evidence_refs: string[] }>; missing_metrics: string[]; trends: Array<{ metric: string; points: number; direction: string; delta: number | null; unit: string | null; evidence_refs: string[] }>; derived_metrics: Array<{ code: string; value: number | null; unit: string | null; formula: string; evidence_refs: string[]; status: string; limitation: string }>; limitations: string[]; provenance_hash: string; synthetic_only: true; clinical_use_authorized: false; human_review_required: true };

const API_URL = (process.env.NEXT_PUBLIC_WYSH_AI_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers || {}) }, cache: "no-store" });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json() as Promise<T>;
}

export const api = {
  url: API_URL,
  patients: () => request<{ synthetic_only: true; patients: PatientSummary[] }>("/v1/console/synthetic-patients"),
  patient: (id: string) => request<PatientCase>(`/v1/console/synthetic-patients/${encodeURIComponent(id)}`),
  assess: (disease_id: string, measurements: Measurement[]) => request<Assessment>("/v1/disease-intelligence/clinical-assess", { method: "POST", body: JSON.stringify({ tenant_id: "synthetic-console-tenant", patient_id: "synthetic-console-patient", disease_id, measurements, synthetic: true }) }),
  calculate: (disease_id: string, measurements: Measurement[]) => request<VerifiedCalculation>("/v1/disease-intelligence/verified-calculations", { method: "POST", body: JSON.stringify({ tenant_id: "synthetic-console-tenant", patient_id: "synthetic-console-patient", disease_id, measurements, synthetic: true }) }),
  diseaseSpecific: (disease_id: string, measurements: Measurement[]) => request<DiseaseSpecific>("/v1/disease-intelligence/disease-specific", { method: "POST", body: JSON.stringify({ tenant_id: "synthetic-console-tenant", patient_id: "synthetic-console-patient", disease_id, measurements, synthetic: true }) }),
  health: () => request<{ status: string; clinical_use_authorized: false; providers: Record<string, unknown> }>("/health"),
  models: () => request<Record<string, unknown>>("/v1/models"),
  evaluation: () => request<EvaluationStatus>("/v1/console/evaluation-status"),
  ruleGovernanceStatus: () => request<RuleGovernanceStatus>("/v1/clinical-rule-governance/status"),
  fhir: (disease_id: string, bundle: Record<string, unknown>) => request<MonitoringResponse>("/v1/disease-intelligence/fhir/monitor", { method: "POST", body: JSON.stringify({ tenant_id: "synthetic-console-tenant", patient_id: "synthetic-console-patient", disease_id, bundle, synthetic: true }) }),
  createReview: (assessment: Assessment, token: string) => request<ClinicalReview>("/v1/clinical-reviews", { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ tenant_id: "synthetic-console-tenant", patient_id: "synthetic-console-patient", disease_id: assessment.disease_id, assessment_id: assessment.assessment_id, assessment_input_hash: assessment.provenance.input_hash, synthetic: true }) }),
  decideReview: (review: ClinicalReview, action: "approve" | "reject" | "request_revision", token: string, note?: string) => request<ClinicalReview>(`/v1/clinical-reviews/${encodeURIComponent(review.review_id)}/decision`, { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ tenant_id: review.tenant_id, patient_id: review.patient_id, expected_version: review.version, action, note, synthetic: true }) }),
};
