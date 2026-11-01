"""Exercise every adapter over real loopback HTTP using synthetic responses.

This is transport/contract evidence only. It is reported as
PASS_LOCAL_EMULATOR and must never be confused with a real provider smoke test.
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
from app.providers import GeminiProvider, MedGemmaProvider, OpenAICompatibleProvider
from app.trion import TrionClient


class SyntheticHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, payload: dict[str, object], status: int = 200) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/tags":
            self._send({"models": [{"name": "medgemma:4b"}]})
            return
        if self.path == "/v1/models":
            self._send({"object": "list", "data": [{"id": "local-medgemma"}]})
            return
        self._send({"error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        path = urlsplit(self.path).path
        response_text = '{"selected_option":"routine","rationale":"Synthetic local contract response.","abstained":false}'
        if path.endswith(":generateContent"):
            self._send({"candidates": [{"content": {"parts": [{"text": response_text}]}}], "usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 5}})
            return
        if path == "/api/chat":
            self._send({"message": {"content": response_text}, "prompt_eval_count": 4, "eval_count": 5})
            return
        if path == "/v1/chat/completions":
            self._send({"choices": [{"message": {"content": response_text}}], "usage": {"prompt_tokens": 4, "completion_tokens": 5}})
            return
        if path == "/v1/clinical/fhir-draft":
            required = {"authorization", "x-correlation-id", "idempotency-key"}
            if not required.issubset({key.lower() for key in self.headers}):
                self._send({"error": "missing boundary headers"}, 401)
                return
            self._send({"schemaVersion": 1, "documentId": "synthetic-doc", "resources": [], "generatedBy": "TRION", "model": "trion-local"})
            return
        self._send({"error": "not found"}, 404)

    def log_message(self, *_args: object) -> None:
        return


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), SyntheticHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        common = dict(provider_timeout_ms=2000, provider_max_retries=0)
        gemini = GeminiProvider(Settings(**common, gemini_api_key="synthetic-only", gemini_api_base=f"{base}/v1beta"))
        medgemma = MedGemmaProvider(Settings(**common, medgemma_base_url=base, medgemma_model="medgemma:4b"))
        compatible = OpenAICompatibleProvider(Settings(**common, openai_compatible_base_url=base, openai_compatible_model="local-medgemma"))
        trion = TrionClient(Settings(**common, trion_enabled=True, trion_base_url=base, trion_api_key="synthetic-only"))
        results = []
        for name, call in ((
            ("gemini", lambda: gemini.infer("synthetic", DecisionModelOutput)),
            ("medgemma", lambda: medgemma.infer("synthetic", DecisionModelOutput)),
            ("openai-compatible", lambda: compatible.infer("synthetic", DecisionModelOutput)),
        )):
            output, telemetry = call()
            results.append({"integration": name, "status": "PASS_LOCAL_EMULATOR", "model_id": telemetry.model, "schema_validated": telemetry.schema_validated, "selected_option": output.selected_option})
        result = trion.execute({"schemaVersion": 1, "documentId": "synthetic-doc"}, correlation_id="local-correlation", idempotency_key="local-idempotency")
        results.append({"integration": "trion", "status": "PASS_LOCAL_EMULATOR", "response_schema": result.payload.get("schemaVersion"), "generated_by": result.payload.get("generatedBy")})
        evidence = {"suite": "synthetic-local-provider-http-e2e", "synthetic_only": True, "status": "PASS", "evidence": results}
    finally:
        server.shutdown()
        server.server_close()
    output = Path(__file__).parents[3] / "artifacts" / "r1-test-evidence" / "local-provider-http-e2e.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_file": str(output), **evidence}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
