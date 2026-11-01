"""Verify the active wysh.AI engineering objective from repository evidence.

This gate is deliberately conservative: it can establish engineering invariants,
not clinical efficacy, regulatory approval, or live provider connectivity.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).parents[3]
API_ROOT = ROOT / "apps/api"
sys.path.insert(0, str(API_ROOT))

from app.config import Settings  # noqa: E402
from app.decision import DecisionModelOutput  # noqa: E402
from app.gateway import ModelGateway  # noqa: E402
from app.main import create_app  # noqa: E402
from app.providers import ProviderError  # noqa: E402
from app.registry import load_registry  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


REQUIRED_FILES = (
    "apps/api/app/gateway.py",
    "apps/api/app/providers.py",
    "apps/api/app/decision.py",
    "apps/api/app/bridge_service.py",
    "apps/api/app/wyshcare_adapter.py",
    "apps/api/app/clinical_orchestration.py",
    "apps/api/app/audit.py",
    "packages/contracts/model-registry.json",
    "packages/contracts/wyshcare-ai-bridge-v1.schema.json",
    "docs/integration/MODEL_CONNECTIVITY_MATRIX.md",
)


def check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {"check": name, "status": "PASS" if passed else "FAIL", "detail": detail}


def main() -> int:
    checks: list[dict[str, str]] = []
    checks.append(check("required implementation artifacts", all((ROOT / path).exists() for path in REQUIRED_FILES), "gateway, providers, decision, bridge, audit, registry and documentation present"))

    defaults = Settings()
    checks.append(check("safe defaults", defaults.allow_cloud_fallback is False and defaults.inference_enabled is False and defaults.enabled_model_ids == frozenset(), "cloud fallback, inference and runtime model allowlist are disabled by default"))
    unsafe_settings = Settings(openai_compatible_base_url="http://user:secret@local.test", openai_compatible_model="synthetic-model", enabled_model_ids=frozenset({"synthetic-model"}), inference_enabled=True)
    try:
        ModelGateway(unsafe_settings).infer("openai-compatible", "synthetic", DecisionModelOutput)
    except ProviderError as exc:
        endpoint_gate_passed = exc.classification == "invalid_configuration"
    else:
        endpoint_gate_passed = False
    checks.append(check("endpoint configuration fail-closed", endpoint_gate_passed, "embedded endpoint credentials are rejected before provider invocation"))

    registry = load_registry()
    checks.append(check("clinical promotion boundary", all(item.clinical_approved is False for item in registry.models), "no registry model is clinically approved"))
    checks.append(check("synthetic bridge contract", json.loads((ROOT / "packages/contracts/wyshcare-ai-bridge-v1.schema.json").read_text(encoding="utf-8")).get("properties", {}).get("synthetic", {}).get("const") is True, "bridge schema requires synthetic=true"))

    test_run = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=API_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    checks.append(check("backend regression", test_run.returncode == 0, test_run.stdout.strip().splitlines()[-1] if test_run.stdout.strip() else f"pytest exit {test_run.returncode}"))

    console_root = ROOT / "apps/clinical-console"
    console_typecheck = subprocess.run(["npm", "run", "typecheck"], cwd=console_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    console_build = subprocess.run(["npm", "run", "build"], cwd=console_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    checks.append(check("clinical console typecheck", console_typecheck.returncode == 0, "Next.js TypeScript contract check"))
    checks.append(check("clinical console build", console_build.returncode == 0, "Next.js production build"))

    runtime_app = create_app(Settings())
    runtime_client = TestClient(runtime_app)
    decision_payload = {
        "tenant_id": "synthetic-objective-tenant",
        "patient_id": "synthetic-objective-patient",
        "question": "Which administrative queue should receive this intake?",
        "permitted_options": ["routine", "review"],
        "synthetic": True,
    }
    first = runtime_client.post("/v1/decisions", headers={"Idempotency-Key": "objective-decision-1"}, json=decision_payload)
    replay = runtime_client.post("/v1/decisions", headers={"Idempotency-Key": "objective-decision-1"}, json=decision_payload)
    conflict_payload = {**decision_payload, "question": "Which workflow queue should receive this intake?"}
    conflict = runtime_client.post("/v1/decisions", headers={"Idempotency-Key": "objective-decision-1"}, json=conflict_payload)
    checks.append(check("decision replay protection", first.status_code == 200 and replay.status_code == 200 and first.json() == replay.json() and conflict.status_code == 409, "same identity replays deterministically and conflicting content is rejected"))
    checks.append(check("decision telemetry", first.status_code == 200 and first.json().get("telemetry", {}).get("status") == "policy_abstained", "policy abstention returns sanitized telemetry"))
    checks.append(check("audit hash chain", runtime_app.state.audit_sink.chain_is_valid(), "redacted runtime audit events form a valid chain"))
    readiness = runtime_client.get("/v1/models/readiness")
    checks.append(check("provider readiness redaction", readiness.status_code == 200 and "API_KEY" not in readiness.text and readiness.json().get("clinical_use_authorized") is False, "readiness is redacted and non-authorizing"))

    live_path = ROOT / "artifacts/r7-test-evidence/r7d-live-medgemma-gate.json"
    live_status = json.loads(live_path.read_text(encoding="utf-8")).get("status") if live_path.exists() else "MISSING"
    checks.append({"check": "current live MedGemma evidence", "status": "PASS" if live_status == "PASS" else ("BOUNDARY" if live_status == "BLOCKED" else "FAIL"), "detail": f"R7D live gate status: {live_status}; fixture fallback is not permitted"})

    evidence_paths = (ROOT / "artifacts/integration/wyshcare-ai-bridge-gate.json", ROOT / "artifacts/integration/wyshcare-emulator-lane.json", ROOT / "artifacts/integration/wyshcare-authorization-parity.json")
    evidence_ok = True
    evidence_detail = []
    for path in evidence_paths:
        if not path.exists():
            evidence_ok = False
            evidence_detail.append(f"missing:{path.name}")
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        passed = document.get("status") == "PASS" and document.get("synthetic_only") is True and document.get("clinical_use_authorized") is False and document.get("wyshcare_modified") is False
        evidence_ok = evidence_ok and passed
        evidence_detail.append(f"{path.name}:{document.get('status')}")
    checks.append(check("integration evidence", evidence_ok, ", ".join(evidence_detail)))

    e2e_path = ROOT / "artifacts/integration/worldclass-synthetic-e2e.json"
    e2e_document = json.loads(e2e_path.read_text(encoding="utf-8")) if e2e_path.exists() else {}
    e2e_ok = (
        e2e_document.get("status") == "PASS"
        and e2e_document.get("synthetic_only") is True
        and e2e_document.get("model_execution") == "NOT_RUN_CONTRACT_HARNESS"
        and e2e_document.get("fixture_fallback_used") is False
        and e2e_document.get("clinical_use_authorized") is False
        and e2e_document.get("production") == "NO-GO"
        and e2e_document.get("wyshcare_modified") is False
    )
    checks.append(check("cross-cutting synthetic E2E evidence", e2e_ok, "policy, bridge, TRION, review, unsafe-output, production-isolation, and metrics-redaction checks pass"))

    adapter_path = ROOT / "artifacts/r1-test-evidence/local-provider-http-e2e.json"
    adapter_document = json.loads(adapter_path.read_text(encoding="utf-8")) if adapter_path.exists() else {}
    adapter_integrations = {item.get("integration") for item in adapter_document.get("evidence", []) if item.get("status") == "PASS_LOCAL_EMULATOR"}
    checks.append(check("adapter contract evidence", adapter_document.get("status") == "PASS" and adapter_integrations == {"gemini", "medgemma", "openai-compatible", "trion"}, "all four provider/boundary adapters pass the synthetic loopback harness"))

    routing_path = ROOT / "artifacts/r1-test-evidence/routing-trace-gate.json"
    routing_document = json.loads(routing_path.read_text(encoding="utf-8")) if routing_path.exists() else {}
    route_attempts = routing_document.get("route_attempts", [])
    routing_ok = (
        routing_document.get("status") == "PASS"
        and routing_document.get("synthetic_only") is True
        and routing_document.get("metrics_redacted") is True
        and routing_document.get("clinical_use_authorized") is False
        and [item.get("status") for item in route_attempts] == ["failure", "success"]
    )
    checks.append(check("sanitized routing trace evidence", routing_ok, "local-first failure-to-success route is recorded without request content"))

    release_path = ROOT / "artifacts/r1-test-evidence/verification-summary.json"
    release_document = json.loads(release_path.read_text(encoding="utf-8")) if release_path.exists() else {}
    release_checks_pass = all(item.get("status") == "PASS" for item in release_document.get("checks", []))
    checks.append(check("aggregate release suite", release_checks_pass and not release_document.get("failed_integrations"), f"release status: {release_document.get('status', 'MISSING')}"))

    status = "PASS_WITH_BOUNDARIES" if all(item["status"] in {"PASS", "BOUNDARY"} for item in checks) else "FAIL"
    report = {
        "schema_version": "wysh-ai-objective-gate-v1",
        "status": status,
        "scope": "isolated synthetic engineering only",
        "clinical_use_authorized": False,
        "clinical_validation": "NO-GO",
        "production": "NO-GO",
        "wyshcare_modified": False,
        "checks": checks,
    }
    output = ROOT / "artifacts/objective-gate/objective-gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "output": str(output)}))
    return 0 if status != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
