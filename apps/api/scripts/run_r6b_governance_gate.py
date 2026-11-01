"""Run the synthetic R6B rule lifecycle and evaluator-hardening gate."""

from __future__ import annotations

import json
from pathlib import Path

from app.approved_clinical_rules import evaluate_diabetes_hypoglycemia
from app.disease_intelligence import LongitudinalMeasurement
from app.disease_specific_intelligence import DiseaseSpecificRequest
from app.rule_governance_store import RuleConflict, RuleGovernanceStore, RuleValidationError


def measurement(mid: str, value: float) -> LongitudinalMeasurement:
    return LongitudinalMeasurement(measurement_id=mid, metric="glucose", value=value, unit="mg/dL", observed_at="2026-10-01T00:00:00Z", source_type="observation")


def main() -> int:
    root = Path(__file__).parents[3]
    store = RuleGovernanceStore(":memory:")
    checks: dict[str, bool] = {}
    try:
        rule = store.create(tenant_id="synthetic-r6b-tenant", rule_id="diabetes.hypoglycemia-observation", rule_version="r6b-diabetes-hypoglycemia-v1", disease_id="diabetes", evidence_id="ada-soc-2026-hypoglycemia", intended_use="synthetic observation classification", revision_hash="sha256:synthetic", expires_at="2030-01-01T00:00:00Z", actor_subject="synthetic-engineer")
        reviewed = store.transition(tenant_id=rule.tenant_id, rule_id=rule.rule_id, expected_version=1, action="submitted", evidence_id=rule.evidence_id, actor_subject="synthetic-engineer", actor_role="rule-engineer")
        checks["draft_to_reviewed"] = reviewed.status == "REVIEWED"
        try:
            store.transition(tenant_id=rule.tenant_id, rule_id=rule.rule_id, expected_version=2, action="approved", evidence_id="wrong-evidence", actor_subject="synthetic-reviewer", actor_role="clinical-reviewer")
        except RuleValidationError:
            checks["evidence_binding_fail_closed"] = True
        approved = store.transition(tenant_id=rule.tenant_id, rule_id=rule.rule_id, expected_version=2, action="approved", evidence_id=rule.evidence_id, actor_subject="synthetic-reviewer", actor_role="clinical-reviewer")
        active = store.transition(tenant_id=rule.tenant_id, rule_id=rule.rule_id, expected_version=3, action="activated", evidence_id=rule.evidence_id, actor_subject="synthetic-governance", actor_role="clinical-governance")
        checks["reviewed_to_approved_to_active"] = approved.status == "APPROVED" and active.status == "ACTIVE"
        try:
            store.transition(tenant_id=rule.tenant_id, rule_id=rule.rule_id, expected_version=3, action="revoked", evidence_id=rule.evidence_id, actor_subject="synthetic-governance", actor_role="clinical-governance")
        except RuleConflict:
            checks["replay_fail_closed"] = True
        revoked = store.transition(tenant_id=rule.tenant_id, rule_id=rule.rule_id, expected_version=4, action="revoked", evidence_id=rule.evidence_id, actor_subject="synthetic-governance", actor_role="clinical-governance")
        checks["active_to_revoked"] = revoked.status == "REVOKED"
        req = DiseaseSpecificRequest(tenant_id="synthetic-r6b-tenant", patient_id="synthetic-r6b-patient", disease_id="diabetes", measurements=[measurement("g1", 65)], synthetic=True)
        checks["rule_remains_engineering_only"] = evaluate_diabetes_hypoglycemia(req).approval_status == "ENGINEERING_ONLY"
        conflict = DiseaseSpecificRequest(tenant_id=req.tenant_id, patient_id=req.patient_id, disease_id=req.disease_id, measurements=[measurement("g2", 65), measurement("g3", 53)], synthetic=True)
        conflict.measurements[1] = conflict.measurements[1].model_copy(update={"observed_at": conflict.measurements[0].observed_at})
        checks["conflicting_observations_abstain"] = evaluate_diabetes_hypoglycemia(conflict).abstained
    finally:
        store.close()
    payload = {"suite": "synthetic-r6b-rule-governance-gate", "status": "PASS" if all(checks.values()) and len(checks) == 7 else "FAIL", "checks": checks, "clinical_approval_claimed": False, "clinical_governance": "HOLD", "clinical_validation": "NO-GO", "production": "NO-GO", "synthetic_only": True}
    output = root / "artifacts/r6-test-evidence/r6b-governance-gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), **payload}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
