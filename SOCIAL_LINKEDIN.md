WyshCare is open-sourcing wysh.AI — our preclinical clinical intelligence service (WMI-1). 🏥

It is a standalone, safety-first service for governed clinical snapshot decisions. Built with Python FastAPI, Pydantic, and Uvicorn. Adapters include MedGemma, OpenAI-compatible, Gemini, and the WyshCare TRION boundary. Gateway authentication uses signed JWKS RS256 service tokens. Model registry entries are EXPERIMENTAL only; no automated or synthetic workflow can set CLINICALLY_APPROVED.

Key boundaries: synthetic-only development context, deny-by-default production inference, and explicit abstention when evidence is missing or unsafe. 185 backend tests pass; the objective gate reports PASS_WITH_BOUNDARIES.

Important: wysh.AI is preclinical engineering. It is not approved for patient care, and clinical validation and production deployment remain NO-GO.

We're building in public. Star, fork, and contribute: https://github.com/vimarshakk/wysh.AI

#OpenSource #ClinicalAI #HealthcareAI #Python #FastAPI #WyshCare #PatientSafety