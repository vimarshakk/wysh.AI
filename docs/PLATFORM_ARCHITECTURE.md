# wysh.AI platform architecture

wysh.AI is the governed AI plane for every WyshCare application. Applications do not choose a model directly. They choose a capability and an application profile; the plane applies authorization, evidence rules, routing, structured output validation, provenance, abstention, review requirements, and telemetry before a provider is called.

```text
WyshCare apps
    │ signed gateway token + capability request
    ▼
wysh.AI API plane
    ├── tenant/patient authorization
    ├── application profile + policy gate
    ├── evidence grounding + provenance
    ├── model gateway / structured-output validator
    ├── abstention + clinician review boundary
    └── audit / metrics / evaluation gates
    ▼
local or self-hosted model endpoints
    ├── Ollama (developer and workstation lane)
    ├── vLLM (GPU serving and scale lane)
    ├── llama.cpp (portable edge lane)
    └── optional Gemini / verified TRION boundaries
```

## Capability lanes

- Patient companion: education and navigation only; no diagnosis, prescribing, triage, or emergency decisions.
- Clinician copilot: snapshots, evidence grounding, workflow decisions, and human review; clinical authorization remains false.
- Care navigation: routing and follow-up workflow support with explicit evidence and review.
- Operations: bounded workflow classification and summarization, with no patient-care claims.
- Research: synthetic evaluation and evidence-grounding experiments isolated from live care.

## Model strategy

MedGemma is the medical-language lane and is currently verified locally through Ollama with synthetic requests. General open models remain disabled in the registry until their exact runtime, license, prompt policy, and evaluation evidence are recorded. vLLM is the preferred GPU serving interface because its OpenAI-compatible server supports structured outputs; Ollama is the simplest local path and supports JSON Schema structured outputs; llama.cpp is the portable edge option.

The model registry is intentionally deny-by-default. A model becomes runtime-enabled only when it is both manifest-enabled and explicitly listed in `MODEL_ENABLED_IDS`. Clinical approval is a separate field and remains false for every current model.

## Security posture

The current plane is preclinical and synthetic-only. Production mode returns a fail-closed response for inference and grounding. No raw document payloads, PHI, credentials, or provider responses are persisted by the local audit sink. A production implementation still needs managed audit storage, gateway-issued asymmetric tokens, consent enforcement in WyshCare, data retention controls, incident response, independent clinical evaluation, and formal release approval.
