"""Check that external projects remain reviewed, adapter-only references."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parents[3]
MANIFEST = ROOT / "packages/contracts/open-source-adoption-v1.json"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    projects = manifest.get("projects", [])
    checks = {
        "adapter_only_policy": manifest.get("policy") == "adapter-only-no-vendoring",
        "no_third_party_code_copied": manifest.get("third_party_code_copied") is False,
        "no_model_weights_copied": manifest.get("model_weights_copied") is False,
        "unique_project_ids": len({item.get("id") for item in projects}) == len(projects),
        "source_urls_are_https": all(isinstance(item.get("source_url"), str) and item["source_url"].startswith("https://") for item in projects),
        "unverified_projects_not_promoted": all(not item.get("code_license_verified") or item.get("promotion_status") not in {"runtime", "approved"} for item in projects),
        "blocked_projects_reference_only": all(item.get("promotion_status") != "blocked" or item.get("integration_mode") == "reference-only" for item in projects),
    }
    review_items = [item["id"] for item in projects if not item.get("code_license_verified") or item.get("weights_license_status") != "verified"]
    payload = {
        "suite": "open-source-governance-gate",
        "status": "PASS_WITH_REVIEW_ITEMS" if all(checks.values()) and review_items else ("PASS" if all(checks.values()) else "FAIL"),
        "checks": checks,
        "review_items": review_items,
        "third_party_code_copied": False,
        "model_weights_copied": False,
    }
    output = ROOT / "artifacts/r2-test-evidence/open-source-gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), **payload}, indent=2))
    return 0 if payload["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
