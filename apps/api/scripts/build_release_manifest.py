"""Build a deterministic, sanitized manifest for an isolated release candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
from typing import Iterable

ROOT = Path(__file__).parents[3]
OUTPUT = ROOT / "artifacts/opensource-release/release-manifest.json"
EVIDENCE_FILES = (
    "artifacts/objective-gate/objective-gate.json",
    "artifacts/r7-test-evidence/r7d-live-medgemma-gate.json",
    "artifacts/r14-test-evidence/r14-acceptance.json",
    "artifacts/integration/worldclass-synthetic-e2e.json",
    "artifacts/integration/wyshcare-authorization-parity.json",
    "artifacts/opensource-release/dependency-inventory.json",
    "artifacts/opensource-release/release-gate.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def evidence_inventory(paths: Iterable[str]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for relative in paths:
        path = ROOT / relative
        if path.is_file():
            records.append({"path": relative, "status": "PRESENT", "sha256": sha256(path), "bytes": path.stat().st_size})
        else:
            records.append({"path": relative, "status": "MISSING"})
    return records


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "wysh-ai-release-manifest-v1",
        "manifest_scope": "isolated_engineering_release_candidate",
        "generated_by": "apps/api/scripts/build_release_manifest.py",
        "network_access": False,
        "source_publication": "NOT_PERFORMED",
        "clinical_use_authorized": False,
        "clinical_validation": "NO-GO",
        "production_deployment": "NO-GO",
        "wyshcare_modifications": False,
        "runtime": {"python": platform.python_version(), "platform": platform.platform(), "api_package": "wysh-ai-api", "api_version": "0.1.0"},
        "evidence": evidence_inventory(EVIDENCE_FILES),
        "rights_and_governance": {
            "project_license_owner_approved": False,
            "python_lock_or_sbom_approved": False,
            "dataset_rights_approved": False,
            "model_weight_rights_approved": False,
            "independent_clinical_validation": False,
        },
        "release_action": {
            "publication_performed": False,
            "files_deleted": False,
            "external_services_contacted": False,
            "note": "Evidence index only; no publication or clinical-use authorization.",
        },
    }
    OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "MANIFEST_WRITTEN", "output": str(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
