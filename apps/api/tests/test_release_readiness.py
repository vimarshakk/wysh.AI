from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load_script(name: str, relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_manifest_is_explicitly_non_authorizing() -> None:
    script = load_script("build_release_manifest", "scripts/build_release_manifest.py")
    assert script.main() == 0
    manifest = json.loads((script.ROOT / "artifacts/opensource-release/release-manifest.json").read_text())
    assert manifest["clinical_use_authorized"] is False
    assert manifest["production_deployment"] == "NO-GO"
    assert manifest["source_publication"] == "NOT_PERFORMED"
    assert manifest["wyshcare_modifications"] is False
    assert any(item["path"].endswith("objective-gate.json") for item in manifest["evidence"])


def test_release_gate_inventory_is_bounded() -> None:
    script = load_script("run_open_source_release_gate", "scripts/run_open_source_release_gate.py")
    artifacts = script.release_artifacts_present()
    assert all(not item.startswith(".venv/") for item in artifacts)
    assert isinstance(artifacts, list)


def test_dependency_inventory_is_network_free_and_structured() -> None:
    script = load_script("run_open_source_release_gate_inventory", "scripts/run_open_source_release_gate.py")
    inventory = script.dependency_inventory()
    assert inventory["network_access"] is False
    assert inventory["manifests"]
    assert all("path" in item and "status" in item for item in inventory["manifests"])
