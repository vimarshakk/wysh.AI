"use client";

import { useEffect, useMemo, useState } from "react";
import { api, type Assessment, type ClinicalReview, type DiseaseSpecific, type EvaluationStatus, type Measurement, type PatientCase, type PatientSummary, type RuleGovernanceStatus, type VerifiedCalculation } from "../lib/api";

type Tab = "workspace" | "import" | "review" | "operations" | "evaluation";
const diseases = ["diabetes", "prediabetes", "hypertension", "dyslipidemia", "obesity", "chronic-kidney-disease", "anemia", "fatty-liver-disease", "copd", "hypothyroidism", "coronary-artery-disease", "heart-failure", "stroke", "asthma", "depression", "anxiety", "osteoarthritis", "pcos", "childhood-undernutrition", "tuberculosis"];

function Pill({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "green" | "amber" | "red" | "blue" }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

function StatusDot({ ok }: { ok: boolean }) { return <span className={`status-dot ${ok ? "status-ok" : "status-off"}`} aria-label={ok ? "available" : "unavailable"} />; }

export default function ClinicalConsole() {
  const [tab, setTab] = useState<Tab>("workspace");
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [patient, setPatient] = useState<PatientCase | null>(null);
  const [disease, setDisease] = useState("diabetes");
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [calculation, setCalculation] = useState<VerifiedCalculation | null>(null);
  const [diseaseSpecific, setDiseaseSpecific] = useState<DiseaseSpecific | null>(null);
  const [health, setHealth] = useState<{ status: string; clinical_use_authorized: false; providers: Record<string, unknown> } | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationStatus | null>(null);
  const [ruleGovernance, setRuleGovernance] = useState<RuleGovernanceStatus | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState<ClinicalReview | null>(null);
  const [reviewToken, setReviewToken] = useState(process.env.NEXT_PUBLIC_CLINICAL_REVIEW_TOKEN || "");
  const [reviewBusy, setReviewBusy] = useState(false);
  const [importText, setImportText] = useState("");
  const [importMessage, setImportMessage] = useState("Paste a synthetic FHIR Bundle to send it through the verified backend adapter.");

  useEffect(() => {
    Promise.all([api.patients(), api.health(), api.evaluation(), api.ruleGovernanceStatus()]).then(([patientResult, healthResult, evaluationResult, ruleGovernanceResult]) => {
      setPatients(patientResult.patients);
      setSelectedId(patientResult.patients[0]?.case_id || "");
      setHealth(healthResult);
      setEvaluation(evaluationResult);
      setRuleGovernance(ruleGovernanceResult);
    }).catch((reason: Error) => setError(`Backend unavailable: ${reason.message}`)).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    api.patient(selectedId).then((result) => { setPatient(result); setDisease(result.disease_id === "chronic-kidney-disease" ? result.disease_id : result.disease_id); setAssessment(null); setCalculation(null); setDiseaseSpecific(null); setReview(null); }).catch((reason: Error) => setError(`Synthetic case unavailable: ${reason.message}`));
  }, [selectedId]);

  const visibleMeasurements = useMemo(() => patient?.measurements || [], [patient]);
  const diseaseLabel = disease === "chronic-kidney-disease" ? "CKD" : disease[0].toUpperCase() + disease.slice(1);

  async function runAssessment() {
    if (!patient) return;
    setBusy(true); setError("");
    try { const [nextAssessment, nextCalculation, nextDiseaseSpecific] = await Promise.all([api.assess(disease, patient.measurements), api.calculate(disease, patient.measurements), api.diseaseSpecific(disease, patient.measurements)]); setAssessment(nextAssessment); setCalculation(nextCalculation); setDiseaseSpecific(nextDiseaseSpecific); setReview(null); }
    catch (reason) { setError(`Assessment unavailable: ${(reason as Error).message}`); }
    finally { setBusy(false); }
  }

  async function importFhir() {
    setBusy(true); setImportMessage("Sending synthetic bundle to the backend FHIR adapter…");
    try {
      const bundle = JSON.parse(importText) as Record<string, unknown>;
      const result = await api.fhir(disease, bundle);
      setImportMessage(`FHIR adapter returned ${result.trends?.length || 0} descriptive trend(s). Clinical interpretation remains disabled.`);
      setTab("workspace");
    } catch (reason) { setImportMessage(`Import unavailable: ${(reason as Error).message}`); }
    finally { setBusy(false); }
  }

  return <main className="console-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">w</div><div><div className="brand-name">wysh<span>.AI</span></div><div className="brand-sub">clinical intelligence</div></div></div>
      <div className="environment"><StatusDot ok={Boolean(health)} /><span>{health ? "LOCAL ENGINE" : "CONNECTING"}</span><span className="environment-lock">SYNTHETIC</span></div>
      <nav aria-label="Console navigation">
        {(["workspace", "import", "review", "operations", "evaluation"] as Tab[]).map((item) => <button key={item} className={`nav-item ${tab === item ? "nav-active" : ""}`} onClick={() => setTab(item)}><span className="nav-icon">{({ workspace: "⌘", import: "↥", review: "✓", operations: "◌", evaluation: "▥" } as Record<Tab, string>)[item]}</span>{({ workspace: "Patient workspace", import: "Data import", review: "Clinician review", operations: "Model operations", evaluation: "Evaluation center" } as Record<Tab, string>)[item]}</button>)}
      </nav>
      <div className="sidebar-footer"><div className="footer-kicker">MODEL LANE</div><div className="footer-value">Independent console</div><div className="footer-note">No WyshCare database connection</div></div>
    </aside>

    <section className="content">
      <header className="topbar"><div><div className="eyebrow">WDI-20 / PHASE 1</div><h1>{tab === "workspace" ? "Clinical intelligence workspace" : ({ import: "Synthetic data import", review: "Clinician review queue", operations: "Model operations", evaluation: "Evaluation center" } as Record<string, string>)[tab]}</h1></div><div className="top-actions"><Pill tone="amber">Clinical use disabled</Pill><Pill tone="blue">Local only</Pill></div></header>
      {error && <div className="error-banner" role="alert"><strong>Connection boundary:</strong> {error}</div>}
      {loading ? <div className="loading-card"><div className="spinner" />Loading the synthetic console surface…</div> : tab === "workspace" ? <Workspace patients={patients} selectedId={selectedId} setSelectedId={setSelectedId} patient={patient} disease={disease} setDisease={setDisease} assessment={assessment} calculation={calculation} diseaseSpecific={diseaseSpecific} busy={busy} runAssessment={runAssessment} /> : tab === "import" ? <ImportPanel text={importText} setText={setImportText} message={importMessage} onImport={importFhir} busy={busy} /> : tab === "review" ? <ReviewPanel assessment={assessment} review={review} setReview={setReview} token={reviewToken} setToken={setReviewToken} busy={reviewBusy} setBusy={setReviewBusy} /> : tab === "operations" ? <Operations health={health} ruleGovernance={ruleGovernance} /> : <Evaluation evaluation={evaluation} />}
    </section>
  </main>;
}

function Workspace({ patients, selectedId, setSelectedId, patient, disease, setDisease, assessment, calculation, diseaseSpecific, busy, runAssessment }: { patients: PatientSummary[]; selectedId: string; setSelectedId: (id: string) => void; patient: PatientCase | null; disease: string; setDisease: (id: string) => void; assessment: Assessment | null; calculation: VerifiedCalculation | null; diseaseSpecific: DiseaseSpecific | null; busy: boolean; runAssessment: () => void }) {
  return <>
    <div className="notice"><span className="notice-icon">✦</span><div><strong>Evaluation environment</strong><span>All records shown here are synthetic fixtures. Results originate from the local FastAPI engine and are not clinical advice.</span></div></div>
    <div className="workspace-grid">
      <section className="card patient-card"><div className="section-label">PATIENT WORKSPACE</div><div className="patient-select-wrap"><label htmlFor="patient">Synthetic patient case</label><select id="patient" value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>{patients.map((item) => <option key={item.case_id} value={item.case_id}>{item.case_id} · {item.disease_id}</option>)}</select></div>{patient && <div className="patient-meta"><div className="avatar">{patient.case_id.split("-")[0].slice(0, 1).toUpperCase()}</div><div><h2>{patient.case_id}</h2><p>Fixture case · {patient.measurement_count} observations</p></div><Pill tone="green">Synthetic</Pill></div>}<div className="mini-stats"><div><span>DATA POINTS</span><strong>{patient?.measurement_count ?? "—"}</strong></div><div><span>EXPECTED STATE</span><strong>{patient?.expected_engineering_status?.replaceAll("_", " ") ?? "—"}</strong></div></div></section>
      <section className="card engine-card"><div className="section-label">DISEASE INTELLIGENCE</div><div className="disease-tabs">{diseases.map((item) => <button key={item} className={disease === item ? "disease-active" : ""} onClick={() => setDisease(item)}>{item === "chronic-kidney-disease" ? "CKD" : item}</button>)}</div><div className="engine-copy"><h2>{disease === "diabetes" ? "Glycaemic longitudinal review" : disease === "hypertension" ? "Blood-pressure follow-up review" : "Renal trajectory review"}</h2><p>Deterministic data-quality findings, evidence references, and a clinician-reviewable draft.</p></div><button className="primary-button" onClick={runAssessment} disabled={!patient || busy}>{busy ? "Running engine…" : `Run ${disease === "chronic-kidney-disease" ? "CKD" : disease} assessment`} <span>→</span></button></section>
    </div>
    <div className="section-heading"><div><div className="section-label">LONGITUDINAL TIMELINE</div><h2>Evidence trail</h2></div><Pill tone="neutral">{patient?.measurements.length || 0} observations</Pill></div>
    <div className="timeline card">{patient?.measurements.map((item, index) => <div className="timeline-row" key={item.measurement_id}><div className="timeline-line"><span className="timeline-dot" />{index < patient.measurements.length - 1 && <span className="timeline-rule" />}</div><div className="timeline-date">{new Date(item.observed_at).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}</div><div className="timeline-event"><strong>{item.metric.replaceAll("_", " ")}</strong><span>{item.value} {item.unit}</span></div><span className="evidence-ref">{item.measurement_id}</span></div>) || <div className="empty-state">Select a synthetic case to inspect its evidence trail.</div>}</div>
    {assessment && <AssessmentPanel assessment={assessment} />}
    {calculation && <CalculationPanel calculation={calculation} />}
    {diseaseSpecific && <DiseaseSpecificPanel result={diseaseSpecific} />}
  </>;
}

function AssessmentPanel({ assessment }: { assessment: Assessment }) {
  const tone = assessment.abstained ? "red" : assessment.follow_up_status === "REVIEW_REQUIRED" ? "amber" : "green";
  return <section className="assessment-card card"><div className="section-heading compact"><div><div className="section-label">BACKEND ASSESSMENT</div><h2>Clinical findings</h2></div><Pill tone={tone}>{assessment.follow_up_status.replaceAll("_", " ")}</Pill></div><div className="finding-list">{assessment.findings.length ? assessment.findings.map((finding) => <div className="finding" key={finding.code}><div className={`finding-icon finding-${finding.severity.toLowerCase()}`}>{finding.severity === "INFO" ? "i" : "!"}</div><div><strong>{finding.code.replaceAll("_", " ")}</strong><p>{finding.message}</p><div className="refs">Evidence · {finding.evidence_refs.join(", ") || "none"}</div></div></div>) : <div className="empty-state">No deterministic findings returned.</div>}</div><div className="provenance"><div><span>ENGINE</span><strong>{assessment.provenance.engine_version}</strong></div><div><span>INPUT HASH</span><strong>{assessment.provenance.input_hash.slice(0, 18)}…</strong></div><div><span>AUTHORIZATION</span><strong>Clinical use disabled</strong></div></div></section>;
}

function CalculationPanel({ calculation }: { calculation: VerifiedCalculation }) {
  return <section className="assessment-card card"><div className="section-heading compact"><div><div className="section-label">R4B VERIFIED CALCULATIONS</div><h2>Transparent calculation outputs</h2></div><Pill tone={calculation.abstained ? "amber" : "blue"}>{calculation.abstained ? "ABSTAINED" : `${calculation.calculations.length} output(s)`}</Pill></div><div className="finding-list">{calculation.calculations.map((item) => <div className="finding" key={item.code}><div className={`finding-icon ${item.status === "CALCULATED" ? "finding-info" : "finding-review"}`}>{item.status === "CALCULATED" ? "∑" : "!"}</div><div><strong>{item.code.replaceAll("_", " ")}{item.value !== null ? ` · ${item.value} ${item.unit || ""}` : ""}</strong><p>{item.limitation}</p><div className="refs">Formula · {item.formula} · Evidence · {item.evidence_refs.join(", ") || "none"}</div></div></div>)}</div><div className="provenance"><div><span>VERSION</span><strong>{calculation.provenance.calculation_version}</strong></div><div><span>INPUT HASH</span><strong>{calculation.provenance.input_hash.slice(0, 18)}…</strong></div><div><span>AUTHORIZATION</span><strong>Clinical use disabled</strong></div></div></section>;
}

function DiseaseSpecificPanel({ result }: { result: DiseaseSpecific }) {
  return <section className="assessment-card card"><div className="section-heading compact"><div><div className="section-label">R5C DISEASE-SPECIFIC WORKFLOW</div><h2>Condition-specific monitoring</h2></div><Pill tone={result.status === "ABSTAINED" ? "red" : "blue"}>{result.status.replaceAll("_", " ")}</Pill></div><div className="finding-list">{result.findings.length ? result.findings.map((finding) => <div className="finding" key={finding.code}><div className={`finding-icon finding-${finding.severity.toLowerCase()}`}>!</div><div><strong>{finding.code.replaceAll("_", " ")}</strong><p>{finding.message}</p><div className="refs">Evidence · {finding.evidence_refs.join(", ") || "none"}</div></div></div>) : <div className="empty-state">No disease-specific data-quality gaps returned.</div>}{result.trends.map((trend) => <div className="finding" key={`trend-${trend.metric}`}><div className="finding-icon finding-info">↗</div><div><strong>{trend.metric.replaceAll("_", " ")} · {trend.direction}</strong><p>{trend.points} point(s){trend.delta !== null ? ` · delta ${trend.delta} ${trend.unit || ""}` : " · more longitudinal data needed"}</p><div className="refs">Evidence · {trend.evidence_refs.join(", ")}</div></div></div>)}</div><div className="provenance"><div><span>PACK</span><strong>{result.pack_version}</strong></div><div><span>INPUT HASH</span><strong>{result.provenance_hash.slice(0, 18)}…</strong></div><div><span>LIMITATION</span><strong>Data quality only</strong></div></div></section>;
}

function ImportPanel({ text, setText, message, onImport, busy }: { text: string; setText: (value: string) => void; message: string; onImport: () => void; busy: boolean }) {
  return <div className="single-column"><section className="card import-card"><div className="section-label">FHIR R4 / SYNTHETIC ONLY</div><h2>Send a typed bundle through the backend adapter</h2><p className="muted">Unknown codes are ignored by the backend. No image bytes, PHI, or production endpoint is accepted.</p><textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={'{\n  "resourceType": "Bundle",\n  "type": "collection",\n  "meta": {"tag": [{"code": "synthetic"}]},\n  "entry": []\n}'} aria-label="Synthetic FHIR bundle" /><div className="import-actions"><button className="primary-button" onClick={onImport} disabled={!text || busy}>{busy ? "Sending…" : "Send to FHIR adapter →"}</button><span className="muted small">{message}</span></div></section></div>;
}

function ReviewPanel({ assessment, review, setReview, token, setToken, busy, setBusy }: { assessment: Assessment | null; review: ClinicalReview | null; setReview: (value: ClinicalReview | null) => void; token: string; setToken: (value: string) => void; busy: boolean; setBusy: (value: boolean) => void }) {
  async function create() { if (!assessment || !token) return; setBusy(true); try { setReview(await api.createReview(assessment, token)); } catch { setReview(null); } finally { setBusy(false); } }
  async function decide(action: "approve" | "reject" | "request_revision") { if (!review || !token) return; setBusy(true); try { setReview(await api.decideReview(review, action, token, action === "request_revision" ? "Synthetic review requires revision." : undefined)); } finally { setBusy(false); } }
  return <div className="single-column"><section className="card review-card"><div className="section-label">PERSISTED REVIEW BOUNDARY</div><h2>Clinician review workspace</h2><div className="review-warning"><strong>{token ? "Authenticated local lane" : "NOT_CONFIGURED"}</strong><span>{token ? "Decisions are sent to FastAPI and recorded with clinician identity, version, and immutable history." : "Set NEXT_PUBLIC_CLINICAL_REVIEW_TOKEN to enable authenticated synthetic review. No approval is simulated."}</span></div><label htmlFor="review-token">Synthetic clinician token</label><input id="review-token" type="password" value={token} onChange={(event) => setToken(event.target.value)} placeholder="Bearer token value" />{assessment ? <><div className="review-summary"><Pill tone={review ? "blue" : "amber"}>{review ? review.state.replaceAll("_", " ") : "Draft only"}</Pill><div><strong>{assessment.disease_id} · {assessment.assessment_id}</strong><p>{assessment.rationale}</p></div></div>{review ? <><div className="review-actions"><button className="review-button" disabled={busy || review.state === "APPROVED" || review.state === "REJECTED"} onClick={() => decide("approve")}>✓ Approve persisted review</button><button className="review-button reject" disabled={busy || review.state === "APPROVED" || review.state === "REJECTED"} onClick={() => decide("reject")}>× Reject persisted review</button><button className="review-button" disabled={busy || review.state === "APPROVED" || review.state === "REJECTED"} onClick={() => decide("request_revision")}>↻ Request revision</button></div><div className="refs">Version {review.version} · {review.events.length} immutable event(s) · actor {review.created_by}</div></> : <button className="primary-button" disabled={!token || busy} onClick={create}>{busy ? "Persisting…" : "Create persisted review →"}</button>}</> : <div className="empty-state">Run an assessment from the Patient workspace to create a reviewable draft.</div>}</section></div>;
}

function Operations({ health, ruleGovernance }: { health: { status: string; clinical_use_authorized: false; providers: Record<string, unknown> } | null; ruleGovernance: RuleGovernanceStatus | null }) {
  const providers = health?.providers || {};
  return <div className="single-column"><section className="card"><div className="section-label">MODEL OPERATIONS</div><h2>Provider and safety posture</h2><div className="ops-grid"><div className="op-row"><StatusDot ok={Boolean(health)} /><span>FastAPI health</span><strong>{health?.status?.toUpperCase() || "UNAVAILABLE"}</strong></div><div className="op-row"><StatusDot ok={Boolean(providers.medgemma_model)} /><span>MedGemma model configured</span><strong>{String(providers.medgemma_model || "NOT CONFIGURED")}</strong></div><div className="op-row"><StatusDot ok={Boolean(providers.gemini_configured)} /><span>Gemini live credential</span><strong>{providers.gemini_configured ? "CONFIGURED" : "DEFERRED"}</strong></div><div className="op-row"><StatusDot ok={Boolean(providers.trion_configured)} /><span>TRION endpoint</span><strong>{providers.trion_configured ? "CONFIGURED" : "DEFERRED"}</strong></div><div className="op-row"><StatusDot ok={Boolean(ruleGovernance)} /><span>Rule governance lifecycle</span><strong>{ruleGovernance?.lifecycle_available ? "AVAILABLE" : "UNAVAILABLE"}</strong></div><div className="op-row"><StatusDot ok={false} /><span>Clinical rule approval</span><strong>{ruleGovernance?.registry_approval_status || "NOT_CONFIGURED"}</strong></div></div><div className="ops-note">Provider and governance states are read from the backend. This console never fabricates availability, clinical approval, or secrets.</div></section></div>;
}

function Evaluation({ evaluation }: { evaluation: EvaluationStatus | null }) {
  const rows = evaluation ? [["WDI program", evaluation.wdi_program_status, "amber"], ["Local API tests", evaluation.local_api_tests, "green"], ["WDI-20 synthetic E2E", evaluation.wdi20_e2e, "green"], ["Phase 1 evaluation", evaluation.phase1_evaluation, "green"], ["Open-source candidates", `${evaluation.candidate_resources} catalogued`, "blue"], ["Clinical validation", evaluation.clinical_validation, "amber"], ["External connectivity", evaluation.external_connectivity, "amber"]] as const : [];
  return <div className="single-column"><section className="card"><div className="section-label">EVIDENCE CENTER</div><h2>Engineering evidence</h2><p className="muted">Read-only status from sanitized local artifacts. This view is not a release gate.</p><div className="evidence-table">{rows.map(([label, value, tone]) => <div className="evidence-row" key={label}><span>{label}</span><Pill tone={tone}>{value}</Pill></div>)}</div>{!evaluation && <div className="empty-state">Evaluation status unavailable from the backend.</div>}</section></div>;
}
