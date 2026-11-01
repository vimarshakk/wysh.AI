# Open-source endpoint setup

wysh.AI can connect to self-hosted inference without changing application code.
The endpoint is always configured explicitly, and the model ID must be both
manifest-enabled and present in `MODEL_ENABLED_IDS` before the gateway can call
it. The examples below are local-only patterns; they do not download a model
or authorize clinical use.

## Ollama / MedGemma

Expose Ollama on its normal local address and set:

```dotenv
MEDGEMMA_BASE_URL=http://127.0.0.1:11434
MEDGEMMA_MODEL=medgemma:4b
MODEL_ROUTING_ORDER=medgemma
MODEL_ENABLED_IDS=medgemma:4b
WMI_INFERENCE_ENABLED=true
```

The adapter checks `GET /api/tags` before inference and sends structured JSON
requests to `POST /api/chat`. A ready Ollama process is not evidence that the
checkpoint is clinically validated. The currently observed local tag is
`medgemma:latest`; always use the exact tag reported by `/api/tags` rather than
assuming the `medgemma:4b` example exists.

Ollama supports JSON Schema structured outputs, which is why the adapter sends
the Pydantic response schema through its `format` field. See the upstream
[Ollama structured outputs documentation](https://ollama.com/blog/structured-outputs).

## vLLM

Point the OpenAI-compatible adapter at the vLLM server:

```dotenv
OPENAI_COMPATIBLE_BASE_URL=http://127.0.0.1:8000
OPENAI_COMPATIBLE_PATH=/v1/chat/completions
OPENAI_COMPATIBLE_MODEL=<served-model-id>
OPENAI_COMPATIBLE_API_KEY=
MODEL_ROUTING_ORDER=openai-compatible
MODEL_ENABLED_IDS=<served-model-id>
WMI_INFERENCE_ENABLED=true
```

The readiness probe uses `/v1/models`; generation uses `/v1/chat/completions`
with a strict JSON-schema response format when the server supports it.
vLLM's OpenAI-compatible server supports structured outputs; see the upstream
[vLLM structured outputs documentation](https://docs.vllm.ai/en/latest/features/structured_outputs/).

## llama.cpp server

The same adapter works with a llama.cpp server exposing the OpenAI-compatible
API:

```dotenv
OPENAI_COMPATIBLE_BASE_URL=http://127.0.0.1:8080
OPENAI_COMPATIBLE_PATH=/v1/chat/completions
OPENAI_COMPATIBLE_MODEL=<served-model-id>
MODEL_ROUTING_ORDER=openai-compatible
MODEL_ENABLED_IDS=<served-model-id>
```

If a runtime does not support strict JSON-schema mode, it must not be promoted
silently. Add a provider-specific compatibility test and retain schema
validation plus abstention at the wysh.AI boundary.

## Verify safely

Use synthetic input only:

```bash
cd apps/api
python scripts/run_promotion_gate.py
python scripts/run_local_provider_e2e.py
python scripts/run_real_smoke.py
```

`run_local_provider_e2e.py` exercises loopback transport with a synthetic
emulator. `run_real_smoke.py` is the only command whose PASS result can be
counted as a real endpoint request; absent infrastructure is recorded as
`BLOCKED`.

Never place provider keys in browser/mobile bundles, commit them, or point the
configuration at production clinical systems during local validation.
