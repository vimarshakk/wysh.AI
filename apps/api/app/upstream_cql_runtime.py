"""Optional bridge to the pinned local CQF JavaScript runtime.

The bridge is synthetic-only and allowlisted. It is intentionally separate
from the native evaluator so runtime availability or output cannot silently
change clinical behavior.
"""

from __future__ import annotations

import json
from pathlib import Path
import os
import resource
import subprocess
from typing import Any, Literal

from pydantic import BaseModel

from .standards_cql import StandardsCqlRequest


class UpstreamCqlRuntimeResponse(BaseModel):
    runtime: Literal["cqframework-cql-execution", "unavailable"]
    runtime_version: str
    status: Literal["EXECUTED_UPSTREAM_RUNTIME", "UNAVAILABLE", "ABSTAINED"]
    result: dict[str, Any] | None
    reason: str
    synthetic_only: Literal[True] = True
    clinical_use_authorized: Literal[False] = False


MAX_REQUEST_BYTES = 200_000
MAX_ELM_BYTES = 75_000
MAX_BUNDLE_ENTRIES = 100
RUNTIME_TIMEOUT_SECONDS = 8
RUNTIME_MEMORY_BYTES = 768 * 1024 * 1024


def _runtime_root() -> Path:
    return Path(__file__).parents[3] / "apps/cql-runtime"


def _limit_child_process() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))


def execute_pinned_runtime(request: StandardsCqlRequest) -> UpstreamCqlRuntimeResponse:
    if request.library_id != "wysh.diabetes.rules" or request.expression_id != "HasGlucoseObservation":
        return UpstreamCqlRuntimeResponse(runtime="unavailable", runtime_version="3.3.2", status="ABSTAINED", result=None, reason="The upstream runtime bridge is restricted to the pinned synthetic diabetes expression.")
    root = _runtime_root()
    script = root / "run.mjs"
    if not script.exists() or not (root / "node_modules/cql-execution").exists() or not (root / "node_modules/cql-exec-fhir").exists():
        return UpstreamCqlRuntimeResponse(runtime="unavailable", runtime_version="3.3.2", status="UNAVAILABLE", result=None, reason="Pinned upstream runtime is not installed in the isolated runtime lane.")
    entries = request.bundle.get("entry", [])
    patient_present = any(isinstance(entry, dict) and isinstance(entry.get("resource"), dict) and entry["resource"].get("resourceType") == "Patient" for entry in entries)
    glucose_observations = [entry["resource"] for entry in entries if isinstance(entry, dict) and isinstance(entry.get("resource"), dict) and entry["resource"].get("resourceType") == "Observation" and any(isinstance(coding, dict) and coding.get("code") == "2339-0" for coding in entry["resource"].get("code", {}).get("coding", []))]
    if not patient_present or not glucose_observations:
        return UpstreamCqlRuntimeResponse(runtime="cqframework-cql-execution", runtime_version="3.3.2", status="ABSTAINED", result=None, reason="Required synthetic Patient and glucose Observation evidence is missing; the bridge abstained before runtime execution.")
    if any(not isinstance(item.get("effectiveDateTime"), str) or not isinstance(item.get("valueQuantity", {}).get("value"), (int, float)) for item in glucose_observations):
        return UpstreamCqlRuntimeResponse(runtime="cqframework-cql-execution", runtime_version="3.3.2", status="ABSTAINED", result=None, reason="A required glucose Observation is missing a valid effective time or numeric value; the bridge abstained before runtime execution.")
    payload = json.dumps({"elm": request.elm, "bundle": request.bundle}, separators=(",", ":"))
    if len(json.dumps(request.elm, separators=(",", ":")).encode()) > MAX_ELM_BYTES or len(payload.encode()) > MAX_REQUEST_BYTES:
        return UpstreamCqlRuntimeResponse(runtime="cqframework-cql-execution", runtime_version="3.3.2", status="ABSTAINED", result=None, reason="The runtime request exceeded the local ELM or request-size limit.")
    if len(request.bundle.get("entry", [])) > MAX_BUNDLE_ENTRIES:
        return UpstreamCqlRuntimeResponse(runtime="cqframework-cql-execution", runtime_version="3.3.2", status="ABSTAINED", result=None, reason="The FHIR Bundle exceeded the local resource-count limit.")
    child_env = os.environ.copy()
    child_env["NODE_OPTIONS"] = "--max-old-space-size=768"
    try:
        completed = subprocess.run(["node", str(script), payload], cwd=root, capture_output=True, text=True, timeout=RUNTIME_TIMEOUT_SECONDS, check=False, env=child_env, preexec_fn=_limit_child_process if os.name == "posix" else None)
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        return UpstreamCqlRuntimeResponse(runtime="unavailable", runtime_version="3.3.2", status="UNAVAILABLE", result=None, reason="Pinned upstream runtime could not be executed within the local timeout.")
    if completed.returncode != 0:
        return UpstreamCqlRuntimeResponse(runtime="cqframework-cql-execution", runtime_version="3.3.2", status="ABSTAINED", result=None, reason="Pinned upstream runtime rejected the synthetic artifact; no fallback was applied.")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return UpstreamCqlRuntimeResponse(runtime="cqframework-cql-execution", runtime_version="3.3.2", status="ABSTAINED", result=None, reason="Pinned upstream runtime returned invalid JSON; no fallback was applied.")
    return UpstreamCqlRuntimeResponse(runtime="cqframework-cql-execution", runtime_version="3.3.2", status="EXECUTED_UPSTREAM_RUNTIME", result=result, reason="Pinned CQF JavaScript runtime executed the synthetic FHIR R4 artifact; output remains engineering evidence only.")
