"""Validate that runtime model promotions are registry-backed and fail closed."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.config import Settings
from app.registry import load_registry


def main() -> int:
    settings = Settings.from_sources()
    registry = load_registry()
    entries = {model.id: model for model in registry.models}
    checks = []
    unknown = sorted(model_id for model_id in settings.enabled_model_ids if model_id not in entries)
    disabled = sorted(model_id for model_id in settings.enabled_model_ids if model_id in entries and not entries[model_id].enabled)
    checks.append({"check": "all runtime IDs are registered", "passed": not unknown, "offending_ids": unknown})
    checks.append({"check": "all runtime IDs are manifest-enabled", "passed": not disabled, "offending_ids": disabled})
    result = {"suite": "model-promotion-gate-r1", "status": "PASS" if all(item["passed"] for item in checks) else "FAIL", "runtime_enabled_ids": sorted(settings.enabled_model_ids), "checks": checks}
    output = Path(__file__).parents[3] / "artifacts" / "r1-test-evidence" / "promotion-gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), **result}, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
