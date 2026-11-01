"""Verify exact upstream runtime versions and npm lockfile integrity metadata."""

from __future__ import annotations

import json
from pathlib import Path


EXPECTED = {
    "node_modules/cql-execution": {"version": "3.3.2", "integrity": "sha512-ljV+vvsk8aefwJzQRDD66exTce+LJ8h6+tzWNwEI+0357ZFoVnAs+M5p6PdgWiSIuhg4ywl/H5l+N7WoQL+ogg==", "license": "Apache-2.0"},
    "node_modules/cql-exec-fhir": {"version": "2.2.0", "integrity": "sha512-6aQwSnwiFBGMWyKPFvj0/A6yl2vCT7/ShlxCBikN/7pdPN7taQmmTMIMFWse05E2hd/8jW4eu+haQ4qPK19w8A==", "license": "Apache-2.0"},
}


def main() -> int:
    root = Path(__file__).parents[3] / "apps/cql-runtime"
    lock = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
    checks = {key: all(lock.get("packages", {}).get(key, {}).get(field) == value for field, value in expected.items()) for key, expected in EXPECTED.items()}
    payload = {"suite": "r7b-cql-runtime-integrity", "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "expected": EXPECTED, "runtime_isolation": True, "synthetic_only": True, "clinical_validation": "NO-GO", "production": "NO-GO"}
    output = Path(__file__).parents[3] / "artifacts/r7-test-evidence/r7b-runtime-integrity.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), **payload}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
