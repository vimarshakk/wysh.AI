"""Fail-closed, network-free open-source publication readiness audit."""

from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).parents[3]
EXCLUDED_SCAN_DIRS = {".git", ".venv", "node_modules", ".next", "build", "dist", "__pycache__", ".pytest_cache"}
RELEASE_ARTIFACT_PATTERNS = (".DS_Store", "*.sqlite3", "*.sqlite3-*", "*.tsbuildinfo")


def dependency_inventory() -> dict[str, object]:
    """Create a lockfile-backed inventory without contacting a package registry."""
    manifests: list[dict[str, object]] = []
    for path in (ROOT / "apps/clinical-console/package-lock.json", ROOT / "apps/cql-runtime/package-lock.json"):
        if not path.is_file():
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            manifests.append({"path": str(path.relative_to(ROOT)), "status": "INVALID_JSON"})
            continue
        packages = document.get("packages", {})
        licenses = sorted({str(item.get("license")) for item in packages.values() if isinstance(item, dict) and item.get("license")})
        missing_license_count = sum(1 for item in packages.values() if isinstance(item, dict) and item.get("name") and not item.get("license"))
        manifests.append({"path": str(path.relative_to(ROOT)), "status": "PARSED", "package_count": max(0, len(packages) - 1), "license_count": len(licenses), "licenses": licenses, "packages_missing_license": missing_license_count})
    python_manifest = ROOT / "apps/api/pyproject.toml"
    manifests.append({"path": str(python_manifest.relative_to(ROOT)), "status": "DECLARATIONS_ONLY", "lockfile": False, "note": "Python dependencies require a lock/SBOM review before publication."})
    return {"schema_version": "wysh-ai-dependency-inventory-v1", "network_access": False, "manifests": manifests}


def release_artifacts_present() -> list[str]:
    found: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in EXCLUDED_SCAN_DIRS for part in path.parts):
            continue
        if any(path.match(pattern) or path.name == pattern for pattern in RELEASE_ARTIFACT_PATTERNS):
            found.append(str(path.relative_to(ROOT)))
    return sorted(found)


def main() -> int:
    required = ["README.md", "docs/SECURITY.md", "docs/OPEN_SOURCE_GOVERNANCE.md", "docs/OPEN_SOURCE_RELEASE_CHECKLIST.md", ".env.example"]
    missing = [path for path in required if not (ROOT / path).is_file()]
    license_present = any((ROOT / name).is_file() for name in ("LICENSE", "LICENSE.md", "LICENSE.txt"))
    secret_hits: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.name == "run_open_source_release_gate.py" or any(part in EXCLUDED_SCAN_DIRS for part in path.parts):
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            secret_hits.append(str(path.relative_to(ROOT)))
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if re.search(r"-----BEGIN .*PRIVATE KEY-----|AIza[0-9A-Za-z_-]{20,}|sk-[A-Za-z0-9]{20,}", text):
            secret_hits.append(str(path.relative_to(ROOT)))

    inventory = dependency_inventory()
    release_artifacts = release_artifacts_present()
    output_dir = ROOT / "artifacts/opensource-release"
    output_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = output_dir / "dependency-inventory.json"
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")

    blockers: list[str] = []
    if missing:
        blockers.append("required release documentation is missing")
    if secret_hits:
        blockers.append("secret-like material detected")
    if not license_present:
        blockers.append("owner-approved license is missing")
    if release_artifacts:
        blockers.append("generated/local release artifacts must be excluded or removed before publication")
    blockers.extend(["Python dependency lock/SBOM review is pending", "dataset rights review is pending", "model-weight rights review is pending"])

    report = {
        "schema_version": "opensource-release-gate-v1",
        "status": "BLOCKED_RELEASE_READINESS" if blockers else "PREPARED_NOT_PUBLISHED",
        "required_files": {"missing": missing, "present": len(required) - len(missing)},
        "license_present": license_present,
        "license_owner_confirmation": False,
        "dependency_and_sbom_review": "LOCAL_INVENTORY_GENERATED",
        "dependency_inventory": str(inventory_path.relative_to(ROOT)),
        "model_weight_rights_review": "PENDING",
        "dataset_rights_review": "PENDING",
        "secret_scan_hits": sorted(set(secret_hits)),
        "release_artifacts": release_artifacts,
        "blockers": blockers,
        "clinical_use_authorized": False,
        "production_deployment": "NO-GO",
        "publication_action_taken": False,
        "release_decision": "Do not publish until the owner confirms the license and all rights/release reviews pass.",
    }
    report_path = output_dir / "release-gate.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(report_path), "dependency_inventory": str(inventory_path)}))
    return 0 if report["status"] == "PREPARED_NOT_PUBLISHED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
