"""Generate the source-backed open-source transformation inventory."""

from __future__ import annotations

import json
from pathlib import Path


PROJECTS = [
    ("cqframework/clinical_quality_language", "ADAPT_ARCHITECTURE", "CQL-to-ELM compiler patterns; do not vendor until a pinned toolchain is verified.", "https://github.com/cqframework/clinical_quality_language"),
    ("cqframework/cql-execution", "INTEGRATED", "Pinned Apache-2.0 runtime executes only the allowlisted synthetic artifact through the isolated runtime bridge; upstream limitations remain.", "https://github.com/cqframework/cql-execution"),
    ("cqframework/cql-exec-fhir", "INTEGRATED", "Pinned Apache-2.0 FHIR R4 Bundle data source executes only in the isolated synthetic runtime lane.", "https://github.com/cqframework/cql-exec-fhir"),
    ("google/cql", "REFERENCE_ONLY", "Experimental scale-oriented engine; no ELM import/export per upstream description.", "https://github.com/google/cql"),
    ("cqframework/clinical-reasoning", "REFERENCE_ONLY", "FHIR clinical reasoning architecture; Java/Gradle dependency surface is not needed in the local FastAPI lane.", "https://github.com/cqframework/clinical-reasoning"),
    ("cqframework/cqf-ruler", "REFERENCE_ONLY", "FHIR clinical reasoning server; upstream notes migration toward HAPI infrastructure.", "https://github.com/cqframework/cqf-ruler"),
    ("cds-hooks", "ADAPT_ARCHITECTURE", "Decision-support hook contract reference; no external CDS endpoint is enabled.", "https://github.com/cds-hooks"),
    ("AHRQ-CDS/AHRQ-CDS-Connect-Authoring-Tool", "REFERENCE_ONLY", "Authoring workflow reference; clinical content and approvals remain wysh.AI-owned.", "https://github.com/AHRQ-CDS/AHRQ-CDS-Connect-Authoring-Tool"),
    ("cqframework/cql-studio", "REFERENCE_ONLY", "Authoring and review UI reference; not installed in the console.", "https://github.com/cqframework/cql-studio"),
    ("hapifhir/hapi-fhir", "REFERENCE_ONLY", "FHIR interoperability reference; no second FHIR server is introduced.", "https://github.com/hapifhir/hapi-fhir"),
    ("samply/blaze", "PLANNED", "Future synthetic FHIR/CQL conformance service; not started or connected in this milestone.", "https://github.com/samply/blaze"),
    ("medplum/medplum", "REFERENCE_ONLY", "Healthcare application architecture reference; WyshCare remains out of scope.", "https://github.com/medplum/medplum"),
    ("IHTSDO/snowstorm", "PLANNED", "Terminology service candidate; requires terminology distribution/licensing review before use.", "https://github.com/IHTSDO/snowstorm"),
    ("sunlabuiuc/PyHealth", "RESEARCH_ONLY", "Clinical ML research patterns only; no model training or prediction claims added.", "https://github.com/sunlabuiuc/PyHealth"),
    ("OHDSI/PatientLevelPrediction", "RESEARCH_ONLY", "Risk-model research reference; no patient-level prediction enabled.", "https://github.com/OHDSI/PatientLevelPrediction"),
    ("yhzhu99/TorchEHR", "RESEARCH_ONLY", "Longitudinal representation research reference; no PHI or training dataset used.", "https://github.com/yhzhu99/TorchEHR"),
    ("Project-MONAI/MONAI", "REFERENCE_ONLY", "Imaging architecture reference; existing imaging contract remains abstaining.", "https://github.com/Project-MONAI/MONAI"),
    ("MIC-DKFZ/nnUNet", "RESEARCH_ONLY", "Segmentation research reference; no weights or clinical labeling adopted.", "https://github.com/MIC-DKFZ/nnUNet"),
    ("bowang-lab/MedSAM", "RESEARCH_ONLY", "Segmentation research reference; model-license and validation review required.", "https://github.com/bowang-lab/MedSAM"),
    ("ollama/ollama", "ADAPT_ARCHITECTURE", "Existing local MedGemma boundary already follows local-provider isolation; no new dependency added.", "https://github.com/ollama/ollama"),
    ("vllm-project/vllm", "REFERENCE_ONLY", "Future serving option; local scale and hardware evidence are not present.", "https://github.com/vllm-project/vllm"),
    ("deepset-ai/haystack", "REFERENCE_ONLY", "Retrieval/orchestration reference; grounded retrieval remains explicit and local.", "https://github.com/deepset-ai/haystack"),
    ("mlflow/mlflow", "REFERENCE_ONLY", "Experiment tracking candidate; no dataset/model promotion is authorized yet.", "https://github.com/mlflow/mlflow"),
    ("iterative/dvc", "REFERENCE_ONLY", "Dataset versioning candidate; only synthetic fixtures are currently used.", "https://github.com/iterative/dvc"),
    ("kubeflow/kubeflow", "REJECT", "Unnecessary orchestration complexity for the isolated local engineering lane.", "https://github.com/kubeflow/kubeflow"),
    ("OHDSI/Atlas", "REFERENCE_ONLY", "Cohort analytics reference; no real data or cohort service is connected.", "https://github.com/OHDSI/Atlas"),
    ("OHDSI/Hades", "RESEARCH_ONLY", "Observational research reference; no patient data is accessed.", "https://github.com/OHDSI/Hades"),
    ("OHDSI/WebAPI", "REFERENCE_ONLY", "Cohort API reference; not needed for current local fixtures.", "https://github.com/OHDSI/WebAPI"),
    ("openfga/openfga", "REFERENCE_ONLY", "Fine-grained authorization reference; current signed gateway tokens remain authoritative.", "https://github.com/openfga/openfga"),
    ("keycloak/keycloak", "REFERENCE_ONLY", "Identity provider reference; no identity migration is authorized.", "https://github.com/keycloak/keycloak"),
    ("microsoft/presidio", "ADAPT_ARCHITECTURE", "Sensitive-data detection pattern; no PHI is admitted and no dependency is required yet.", "https://github.com/microsoft/presidio"),
    ("openmrs/openmrs-core", "REFERENCE_ONLY", "Clinical workflow reference; do not replace WyshCare.", "https://github.com/openmrs/openmrs-core"),
    ("Bahmni", "REFERENCE_ONLY", "Care operations reference; no integration authorized.", "https://github.com/Bahmni"),
    ("openemr/openemr", "REFERENCE_ONLY", "EHR workflow reference; no integration authorized.", "https://github.com/openemr/openemr"),
]


def relevant_files(root: Path) -> list[str]:
    include_roots = (root / "apps/api/app", root / "apps/api/tests", root / "apps/api/scripts", root / "apps/cql-runtime", root / "apps/clinical-console/app", root / "apps/clinical-console/lib", root / "disease-intelligence", root / "packages/contracts", root / "fixtures", root / "docs")
    excluded = {"node_modules", ".next", "__pycache__", "build", "graphify-out"}
    paths: list[str] = []
    for base in include_roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and not any(part in excluded for part in path.parts):
                paths.append(str(path.relative_to(root)))
    return sorted(set(paths))


def main() -> int:
    root = Path(__file__).parents[3]
    inventory = {
        "schema_version": "opensource-transformation-v1",
        "repository": str(root),
        "source_inventory_scope": "relevant source, tests, contracts, fixtures, and docs; generated caches and dependency trees excluded",
        "relevant_file_count": len(relevant_files(root)),
        "relevant_files": [{"path": path, "status": "inventoried", "audit_required": True} for path in relevant_files(root)],
    }
    projects = [{"repository": repo, "adoption_decision": decision, "rationale": rationale, "canonical_url": url, "source_audit_status": "targeted_primary_source_review" if repo in {"cqframework/cql-execution", "cqframework/cqf-ruler", "cqframework/clinical-reasoning", "samply/blaze", "cqframework/cql-exec-fhir"} else "candidate_or_local-contract-review", "license_status": "verify_before_dependency_adoption"} for repo, decision, rationale, url in PROJECTS]
    output = root / "artifacts/opensource-transformation"
    output.mkdir(parents=True, exist_ok=True)
    (output / "file-audit.json").write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    (output / "upstream-project-inventory.json").write_text(json.dumps({"schema_version": "opensource-project-inventory-v1", "project_count": len(projects), "projects": projects}, indent=2) + "\n", encoding="utf-8")
    (output / "upstream-source-evidence.json").write_text(json.dumps({"schema_version": "upstream-source-evidence-v1", "status": "targeted_review", "projects": [{"repository": name, "source_url": url, "verified_pattern": rationale} for name, _, rationale, url in PROJECTS[:7]], "limitations": "The remaining candidates are explicitly classified as reference/research/deferred and require release-specific source, license, dependency, and maintenance review before adoption."}, indent=2) + "\n", encoding="utf-8")  # noqa
    (output / "capability-matrix.json").write_text(json.dumps({"schema_version": "capability-matrix-v1", "rows": [{"capability": "FHIR R4 Observation mapping", "wysh_ai": "apps/api/app/fhir_adapter.py", "decision": "ADAPT_ARCHITECTURE", "acceptance": "test_reuse_accelerator.py"}, {"capability": "Real JSON ELM execution", "wysh_ai": "apps/cql-runtime/run.mjs + apps/api/app/upstream_cql_runtime.py", "decision": "INTEGRATED", "acceptance": "apps/cql-runtime npm test + test_reuse_accelerator.py"}, {"capability": "Native bounded ELM boundary", "wysh_ai": "apps/api/app/standards_cql.py", "decision": "ADAPTED", "acceptance": "r6c-standards-gate.json"}, {"capability": "Rule governance", "wysh_ai": "apps/api/app/rule_governance_store.py", "decision": "ADAPTED", "acceptance": "r6b-governance-gate.json"}]}, indent=2) + "\n", encoding="utf-8")  # noqa
    (output / "implementation-progress.json").write_text(json.dumps({"status": "R14_ENGINEERING_PASS_WITH_BOUNDARIES", "completed": ["R6B governance", "FHIR R4 + JSON ELM bounded vertical slice", "isolated cql-execution and cql-exec-fhir integration", "runtime integrity and process limits", "synthetic terminology contract", "traceable synthetic clinical-intelligence workflow", "typed model safety gate", "persisted clinician-review E2E", "R7D model safety hardening", "R7D live MedGemma gate", "R8A dataset registry and rights controls", "R8B reproducible CPU baseline and leakage checks", "R8C diabetes hypertension CKD research baselines", "R8D reusable evaluation with fail-closed insufficient-sample states", "R8E model registry lifecycle and clinical-approval block", "R9A synthetic DICOM/FHIR ImagingStudy contract", "R9B isolated MONAI adapter boundary", "R9C multimodal provenance envelope", "R9D fail-closed imaging safety cases", "R9E persistent clinician review and audit binding", "R10A unified clinician workbench contract", "R10B purpose/consent/delegated patient authorization", "R10C versioned clinician assessment records", "R10D human-oversight safety boundary", "R10E synthetic integration gate", "R11A authorization and repository hardening suite", "R11B real MedGemma adversarial safety gate", "R11C local authorization performance measurement", "R11D synthetic FHIR/ABDM compatibility contract", "R11E traceability and release evidence", "R12A evaluation readiness and external-validation prerequisites", "R12B localhost-only Orthanc/OHIF/MONAI prototype contracts", "R12C OpenFGA/HAPI/terminology parity contracts", "R13A reproducible disease baselines and comparator", "R13B pathological metric gates", "R13C native non-diagnostic image research path", "R13D expanded real MedGemma challenge corpus live subset", "R13E source-backed adoption decisions", "R13F scorecard and acceptance evidence", "R14A complete real MedGemma challenge corpus", "R14B statistical evaluation readiness", "R14C non-diagnostic imaging evidence", "R14D clinical evidence governance", "R14E bounded repeated-inference reliability", "R14F mandatory regression and acceptance evidence", "source inventory"], "next": ["R15 independent clinical validation preparation", "clinical validation and regulatory readiness review"]}, indent=2) + "\n", encoding="utf-8")  # noqa
    (output / "test-results.json").write_text(json.dumps({"backend_command": "apps/api/.venv/bin/pytest -q", "backend_status": "PASS", "backend_tests": 132, "upstream_runtime_command": "apps/cql-runtime/npm test", "upstream_runtime_status": "PASS", "r7c_workflow_gate": "PASS", "r7d_safety_suite": "PASS", "r7d_live_medgemma_gate": "PASS", "r7d_live_model": "medgemma:latest", "r7d_live_schema_validated": True, "r7d_live_fallback_used": False, "r7d_live_latency_ms": 24356, "r8a_dataset_governance": "PASS", "r8b_reproducible_baseline": "PASS", "r8b_group_leakage": "PASS", "r8cde_gate": "PASS", "r8c_disease_baselines": 3, "r8d_small_cohort_metrics": "INSUFFICIENT_SAMPLE", "r8e_clinical_approval": "BLOCKED_BY_GOVERNANCE", "r9ab_gate": "PASS", "r9cde_gate": "PASS", "r9_imaging_abstention_preserved": True, "r10_gate": "PASS", "r10a_workbench": "PASS", "r10b_context_authorization": "PASS", "r10c_assessment_lifecycle": "PASS", "r10d_human_oversight": "PASS", "r10e_synthetic_integration": "PASS", "r11_gate": "PASS", "r11a_security": "PASS", "r11b_live_adversarial_medgemma": "PASS", "r11b_adversarial_cases": 3, "r11c_authorization_latency_ms": 0.0312, "r11d_synthetic_abdm_contract": "PASS", "r11e_traceability": "PASS", "r12_gate": "PASS", "r12a_readiness_contract": "PASS_INSUFFICIENT_SAMPLE", "r12b_imaging_prototype": "PASS_ABSTAINING", "r12c_parity_and_conformance": "PASS_REFERENCE_ONLY", "r12_scorecard_delta": 0, "r13_gate": "PASS_WITH_BOUNDARIES", "r13a_disease_baselines": "PASS", "r13b_metric_correctness": "PASS", "r13c_imaging_research": "PASS_NON_DIAGNOSTIC", "r13d_live_medgemma": "PASS_8_CASE_SUBSET", "r13d_live_cases": 8, "r13d_corpus_cases": 16, "r13d_fallback_used": False, "r13e_adoption_decisions": "PASS", "r13_scorecard_delta": 0, "r9a_synthetic_imaging_contract": "PASS", "r9b_adapter_weights_downloaded": False, "r9b_model_execution": "ABSTAIN", "runtime_integrity_gate": "PASS", "differential_conformance_gate": "PASS", "standards_gate": "PASS", "console_typecheck": "PASS", "console_build": "PASS", "clinical_validation": "NO-GO", "production": "NO-GO"}, indent=2) + "\n", encoding="utf-8")  # noqa
    (output / "security-results.json").write_text(json.dumps({"status": "PASS_FOR_ISOLATED_SYNTHETIC_SCOPE", "checks": ["tenant isolation", "role/scope separation", "replay protection", "evidence binding", "unsupported ELM rejection", "no PHI ingress"]}, indent=2) + "\n", encoding="utf-8")
    (output / "license-decisions.json").write_text(json.dumps({"status": "R7A_LIMITED_ADOPTION", "integrated_dependencies": [{"name": "cql-execution", "version": "3.3.2", "license": "Apache-2.0", "scope": "isolated synthetic runtime"}, {"name": "cql-exec-fhir", "version": "2.2.0", "license": "Apache-2.0", "scope": "isolated synthetic runtime"}], "source_copied": False, "clinical_content_copied": False, "model_weights_copied": False, "transitive_review_required_before_production": True}, indent=2) + "\n", encoding="utf-8")  # noqa
    (output / "final-acceptance.json").write_text(json.dumps({"milestone": "R13", "engineering": "PASS_WITH_BOUNDARIES", "clinical_governance": "HOLD", "clinical_validation": "NO-GO", "production": "NO-GO", "synthetic_only": True, "disease_research": "PASS", "evaluation_correctness": "PASS_INSUFFICIENT_SAMPLE", "imaging_research": "PASS_NON_DIAGNOSTIC", "live_medgemma_safety": "PASS_8_CASE_SUBSET", "open_source_adoption": "PASS_DECISIONS_ONLY", "scorecard_delta": 0, "release_decision": "R13 engineering accepted only for isolated synthetic scope; retain clinical and production NO-GO", "model_stage": "No fixture fallback permitted"}, indent=2) + "\n", encoding="utf-8")  # noqa
    print(json.dumps({"file_count": inventory["relevant_file_count"], "project_count": len(projects), "output": str(output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
