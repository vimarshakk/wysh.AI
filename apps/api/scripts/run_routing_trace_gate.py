"""Exercise local-first routing and write sanitized route evidence.

The loopback server is synthetic and deliberately makes the first local route
fail before the second local-compatible route succeeds. The artifact contains
only provider/model/status/reason/latency fields; prompts and response bodies
are never written.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from app.config import Settings
from app.decision import DecisionModelOutput
from app.gateway import ModelGateway
from app.metrics import Metrics
from app.registry import ModelEntry, ModelRegistry


class RoutingHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, body: dict[str, object], status: int = 200) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        if urlsplit(self.path).path == "/api/chat":
            self._send({"error": "synthetic route failure"}, 503)
            return
        if urlsplit(self.path).path == "/v1/chat/completions":
            self._send({"choices": [{"message": {"content": '{"selected_option":"routine","rationale":"Synthetic route response.","abstained":false}'}}]})
            return
        self._send({"error": "not found"}, 404)

    def log_message(self, *_args: object) -> None:
        return


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), RoutingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    metrics = Metrics()
    registry = ModelRegistry(
        schema_version="synthetic-routing-trace-v1",
        default_mode="disabled",
        models=[
            ModelEntry(id="medgemma:latest", provider="self_hosted", task="medical_text", enabled=True, clinical_approved=False),
            ModelEntry(id="synthetic-openai-v1", provider="self_hosted", task="structured_workflow_decision", enabled=True, clinical_approved=False),
        ],
    )
    settings = Settings(
        inference_enabled=True,
        model_routing_order=("medgemma", "openai-compatible", "gemini"),
        allow_cloud_fallback=False,
        enabled_model_ids=frozenset({"medgemma:latest", "synthetic-openai-v1"}),
        medgemma_base_url=base,
        medgemma_model="medgemma:latest",
        openai_compatible_base_url=base,
        openai_compatible_model="synthetic-openai-v1",
        provider_timeout_ms=2000,
        provider_max_retries=0,
    )
    try:
        output, telemetry = ModelGateway(settings, registry, metrics).infer(
            "auto", "synthetic routing prompt", DecisionModelOutput,
        )
        trace = [
            {"provider": item.provider, "model": item.model, "status": item.status, "reason": item.reason, "latency_ms": item.latency_ms}
            for item in telemetry.route_attempts
        ]
        passed = (
            output.selected_option == "routine"
            and [item["status"] for item in trace] == ["failure", "success"]
            and trace[0]["reason"] == "http_error"
            and all("prompt" not in json.dumps(item).lower() for item in trace)
        )
        evidence = {
            "schema_version": "routing-trace-gate-v1",
            "suite": "synthetic-local-first-routing-trace",
            "status": "PASS" if passed else "FAIL",
            "synthetic_only": True,
            "route_attempts": trace,
            "selected_provider": telemetry.provider,
            "selected_model": telemetry.model,
            "schema_validated": telemetry.schema_validated,
            "metrics_redacted": all(token not in metrics.render().lower() for token in ("prompt", "clinical", "synthetic")),
            "clinical_use_authorized": False,
            "production": "NO-GO",
        }
    finally:
        server.shutdown()
        server.server_close()
    output_path = Path(__file__).parents[3] / "artifacts" / "r1-test-evidence" / "routing-trace-gate.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output_path), **evidence}, indent=2))
    return 0 if evidence["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
