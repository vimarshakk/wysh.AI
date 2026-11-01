from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_model_readiness_is_redacted_and_does_not_probe_by_default():
    settings = Settings(
        gemini_api_key="secret-gemini-key",
        enabled_model_ids=frozenset({"medgemma:latest", "gemini-2.5-flash"}),
        medgemma_model="medgemma:latest",
    )
    response = TestClient(create_app(settings)).get("/v1/models/readiness")
    assert response.status_code == 200
    body = response.json()
    assert body["probe_local"] is False
    assert body["clinical_use_authorized"] is False
    assert "secret-gemini-key" not in response.text
    medgemma = next(item for item in body["providers"] if item["provider"] == "medgemma")
    gemini = next(item for item in body["providers"] if item["provider"] == "gemini")
    assert medgemma["runtime_enabled"] is True
    assert medgemma["ready"] is None
    assert gemini["configured"] is True
    assert gemini["ready"] is None


def test_local_readiness_probe_is_explicit_and_fail_closed(monkeypatch):
    monkeypatch.setattr("app.main.MedGemmaProvider.ready", lambda self: False)
    settings = Settings(enabled_model_ids=frozenset({"medgemma:latest"}), medgemma_model="medgemma:latest")
    response = TestClient(create_app(settings)).get("/v1/models/readiness?probe_local=true")
    assert response.status_code == 200
    medgemma = next(item for item in response.json()["providers"] if item["provider"] == "medgemma")
    assert medgemma["ready"] is False
    assert medgemma["reason"] == "ollama model unavailable"
