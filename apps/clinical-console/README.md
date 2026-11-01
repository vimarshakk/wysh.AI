# Wysh AI Clinical Console

Standalone local workbench for observing and evaluating the wysh.AI FastAPI intelligence layer. This is not an EHR and does not connect to WyshCare persistence.

## Run locally

Start the API:

```bash
cd apps/api
./.venv/bin/python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Start the console in another terminal:

```bash
cd apps/clinical-console
npm install
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open [http://localhost:3000](http://localhost:3000). Set `NEXT_PUBLIC_WYSH_AI_API_URL` when the API is not at `http://127.0.0.1:8000`.

## Safety boundary

- Only explicit synthetic fixtures are exposed by the console endpoints.
- All clinical findings originate from FastAPI; the browser performs no authoritative clinical calculations.
- Persisted clinician review requires `NEXT_PUBLIC_CLINICAL_REVIEW_TOKEN` containing a local synthetic JWT with `clinical-review:read`, `clinical-review:write`, and the `clinician` role. Without it, the console shows `NOT_CONFIGURED` and never simulates approval.
- Provider availability is read from FastAPI and never fabricated by the UI.
- No production credentials, PHI, WyshCare database connection, Gemini live call, TRION live call, or cloud deployment is used.

## Verified surface

- Synthetic patient workspace with 60 cases.
- Diabetes, hypertension, and CKD assessment views.
- Longitudinal evidence timeline.
- Synthetic FHIR bundle import through the backend adapter.
- Findings, provenance, abstention, and clinical-use status.
- Model operations and evidence dashboards.
