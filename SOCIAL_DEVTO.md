wysh.AI is WyshCare's preclinical clinical intelligence service (WMI-1): a standalone, safety-first service for governed clinical snapshot decisions.

Built with FastAPI, Pydantic, and Uvicorn, it exposes a synthetic-only snapshot API with evidence references, a human-review lifecycle, a model registry, and a TRION tool boundary. Gateway access requires signed JWKS RS256 service tokens validated for issuer, audience, expiry, tenant, and scope. All model registry entries are EXPERIMENTAL; no automated or synthetic workflow can set CLINICALLY_APPROVED.

The service is deny-by-default: production inference is disabled, PHI-like requests are rejected without gateway context, and no model providers are contacted by default. 185 backend tests pass; the aggregate objective gate reports PASS_WITH_BOUNDARIES.

Important: this is preclinical engineering. It is not approved for patient care.

Read more: https://github.com/vimarshakk/wysh.AI