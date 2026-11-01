"""Run the complete synthetic release-check suite and write safe summary evidence."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


CHECKS = (
    ("unit-contract-tests", [sys.executable, "-m", "pytest", "-q"]),
    ("compile-check", [sys.executable, "-m", "compileall", "-q", "app", "scripts", "tests"]),
    ("synthetic-evaluation", [sys.executable, "scripts/run_eval.py"]),
    ("adversarial-safety-evaluation", [sys.executable, "scripts/run_safety_eval.py"]),
    ("security-isolation-gate", [sys.executable, "scripts/run_security_gate.py"]),
    ("clinical-snapshot-e2e", [sys.executable, "scripts/run_clinical_snapshot_e2e.py"]),
    ("local-provider-http-e2e", [sys.executable, "scripts/run_local_provider_e2e.py"]),
    ("model-promotion-gate", [sys.executable, "scripts/run_promotion_gate.py"]),
    ("real-provider-smoke", [sys.executable, "scripts/run_real_smoke.py"]),
)


def main() -> int:
    results = []
    for name, command in CHECKS:
        completed = subprocess.run(command, cwd=Path(__file__).parents[1], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        results.append({"check": name, "status": "PASS" if completed.returncode == 0 else "FAIL", "exit_code": completed.returncode})
    blocked_integrations: list[str] = []
    failed_integrations: list[str] = []
    smoke_path = Path(__file__).parents[3] / "artifacts" / "r1-test-evidence" / "real-provider-smoke.json"
    if smoke_path.exists():
        smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
        for item in smoke.get("evidence", []):
            if item.get("status") == "BLOCKED":
                blocked_integrations.append(str(item.get("integration")))
            elif item.get("status") != "PASS":
                failed_integrations.append(str(item.get("integration")))
    checks_pass = all(item["status"] == "PASS" for item in results)
    if not checks_pass or failed_integrations:
        status = "FAIL"
    elif blocked_integrations:
        status = "PASS_WITH_BLOCKED_REAL_INTEGRATIONS"
    else:
        status = "PASS"
    summary = {"suite": "wysh-ai-r1-release-checks", "status": status, "blocked_integrations": sorted(blocked_integrations), "failed_integrations": sorted(failed_integrations), "checks": results}
    output = Path(__file__).parents[3] / "artifacts" / "r1-test-evidence" / "verification-summary.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), **summary}, indent=2))
    return 0 if summary["status"] != "FAIL" else 1


if __name__ == "__main__":
    sys.exit(main())
