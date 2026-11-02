"""End-to-end integration tests for the wysh.AI System One decision model.

These tests exercise the full REST API through FastAPI's TestClient,
verifying end-to-end flows from request ingestion through model orchestration
to structured response generation.

All tests use synthetic-only data and respect the deny-by-default boundary.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class TestHealthAndReadiness:
    """System health and readiness endpoint tests."""

    def setup_method(self) -> None:
        self.client = TestClient(create_app(Settings()))

    def test_health_endpoint_returns_ok(self) -> None:
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["clinical_use_authorized"] is False

    def test_readiness_endpoint_returns_ok(self) -> None:
        response = self.client.get("/v1/models/readiness")
        assert response.status_code == 200
        data = response.json()
        assert data["clinical_use_authorized"] is False

    def test_metrics_endpoint_returns_prometheus_format(self) -> None:
        response = self.client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
        assert "wysh_ai" in response.text


class TestClinicalSnapshotAPI:
    """Snapshot endpoint tests for the WMI-1 snapshot generation API."""

    def setup_method(self) -> None:
        self.client = TestClient(create_app(Settings()))

    def test_snapshot_request_requires_synthetic_flag(self) -> None:
        response = self.client.post("/v1/snapshots", json={
            "patient_id": "real-patient-1",
            "tenant_id": "real-tenant-1",
        })
        assert response.status_code == 403

    def test_snapshot_requires_valid_context(self) -> None:
        response = self.client.post("/v1/snapshots", json={
            "tenant_id": "real-tenant-1",  # not synthetic-prefixed
            "patient_id": "synthetic-patient-1",
            "synthetic": True,
        })
        assert response.status_code == 400

    def test_snapshot_returns_valid_response(self) -> None:
        response = self.client.post("/v1/snapshots", json={
            "tenant_id": "synthetic-tenant-1",
            "patient_id": "synthetic-patient-1",
            "synthetic": True,
            "facts": [
                {
                    "source_id": "obs-glucose-001",
                    "source_type": "observation",
                    "metric": "glucose",
                    "value": 154.0,
                    "recorded_at": "2026-01-01T00:00:00Z",
                },
                {
                    "source_id": "obs-hba1c-001",
                    "source_type": "observation",
                    "metric": "hba1c_percent",
                    "value": 7.2,
                    "recorded_at": "2026-01-01T00:00:00Z",
                },
            ],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["snapshot_id"].startswith("snapshot-")
        assert data["patient_id"] == "synthetic-patient-1"
        assert data["tenant_id"] == "synthetic-tenant-1"
        assert data["synthetic"] is True
        assert data["human_review_required"] is True
        assert data["clinical_use_authorized"] is False
        assert len(data["facts"]) == 2

    def test_snapshot_provenance_is_deterministic(self) -> None:
        payload = {
            "tenant_id": "synthetic-tenant-1",
            "patient_id": "synthetic-patient-1",
            "synthetic": True,
            "facts": [
                {
                    "source_id": "obs-1",
                    "source_type": "observation",
                    "metric": "hba1c_percent",
                    "value": 7.2,
                    "recorded_at": "2026-01-01T00:00:00Z",
                },
            ],
        }
        r1 = self.client.post("/v1/snapshots", json=payload)
        r2 = self.client.post("/v1/snapshots", json=payload)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["decision_id"] == r2.json()["decision_id"]
        assert r1.json()["feature_hash"] == r2.json()["feature_hash"]

    def test_snapshot_rejects_phi_in_context(self) -> None:
        response = self.client.post("/v1/snapshots", json={
            "tenant_id": "synthetic-tenant-1",
            "patient_id": "synthetic-patient-1",
            "synthetic": True,
            "context": {
                "mrn": "MRN-123456",
                "name": "John Doe",
            },
        })
        assert response.status_code == 400


class TestClinicalDecisionRouter:
    """System One decision router endpoint tests."""

    def setup_method(self) -> None:
        self.client = TestClient(create_app(Settings()))

    def test_decision_requires_synthetic_input(self) -> None:
        response = self.client.post("/v1/decisions", json={
            "tenant_id": "real-tenant-1",
            "patient_id": "real-patient-1",
            "indication": "diabetes",
            "synthetic": False,
            "facts": [],
        })
        assert response.status_code == 403

    def test_decision_returns_structured_output(self) -> None:
        response = self.client.post("/v1/decisions", json={
            "tenant_id": "synthetic-tenant-1",
            "patient_id": "synthetic-patient-1",
            "indication": "diabetes",
            "synthetic": True,
            "facts": [
                {
                    "source_id": "obs-1",
                    "source_type": "observation",
                    "metric": "hba1c_percent",
                    "value": 7.2,
                    "recorded_at": "2026-01-01T00:00:00Z",
                },
            ],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["decision_id"].startswith("decision-")
        assert data["indication"] == "diabetes"
        assert data["model_id"] == "wysh.synthetic.diabetes.review.v1"
        assert data["model_status"] == "EXPERIMENTAL"
        assert data["human_review_required"] is True
        assert data["clinical_use_authorized"] is False
        assert data["system"] == "system_one"
        assert data["latency_ms"] >= 0

    def test_decision_abstains_without_sufficient_evidence(self) -> None:
        response = self.client.post("/v1/decisions", json={
            "tenant_id": "synthetic-tenant-1",
            "patient_id": "synthetic-patient-1",
            "indication": "diabetes",
            "synthetic": True,
            "facts": [],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["abstained"] is True
        assert data["selected_action"] is None
        assert data["confidence"] is None
        assert data["abstention_reason"] is not None


class TestClinicalReview:
    """Clinical review endpoint tests."""

    def setup_method(self) -> None:
        self.client = TestClient(create_app(Settings()))

    def test_submit_clinical_review(self) -> None:
        response = self.client.post("/v1/clinical-reviews", json={
            "review_id": "review-001",
            "model_id": "wysh.synthetic.diabetes.review.v1",
            "decision": "APPROVE",
            "rationale": "Clinical review confirms the decision.",
            "confidence_in_decision": 0.95,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["record_id"] == "review-001"
        assert data["decision"] == "APPROVE"
        assert data["human_review_required"] is True
        assert data["clinical_use_authorized"] is False

    def test_get_clinical_review(self) -> None:
        # First create a review
        create_resp = self.client.post("/v1/clinical-reviews", json={
            "review_id": "review-get-001",
            "model_id": "wysh.synthetic.diabetes.review.v1",
            "decision": "APPROVE",
            "rationale": "Clinical review confirms the decision.",
            "confidence_in_decision": 0.95,
        })
        assert create_resp.status_code == 201

        # Then retrieve it
        response = self.client.get("/v1/clinical-reviews/review-get-001")
        assert response.status_code == 200
        data = response.json()
        assert data["record_id"] == "review-get-001"
        assert data["decision"] == "APPROVE"

    def test_get_nonexistent_review_returns_404(self) -> None:
        response = self.client.get("/v1/clinical-reviews/nonexistent-review")
        assert response.status_code == 404


class TestDiseaseIntelligence:
    """Disease intelligence endpoint tests."""

    def setup_method(self) -> None:
        self.client = TestClient(create_app(Settings()))

    def test_disease_catalog_is_available(self) -> None:
        response = self.client.get("/v1/disease-intelligence/catalog")
        assert response.status_code == 200
        data = response.json()
        assert data["clinical_use_authorized"] is False
        assert len(data["models"]) > 0

    def test_diabetes_disease_workflow(self) -> None:
        response = self.client.post("/v1/disease-intelligence/disease-specific", json={
            "tenant_id": "synthetic-tenant-1",
            "patient_id": "synthetic-patient-1",
            "indication": "diabetes",
            "synthetic": True,
            "facts": [
                {
                    "source_id": "obs-hba1c-001",
                    "source_type": "observation",
                    "metric": "hba1c_percent",
                    "value": 7.2,
                    "recorded_at": "2026-01-01T00:00:00Z",
                },
                {
                    "source_id": "obs-glucose-001",
                    "source_type": "observation",
                    "metric": "glucose",
                    "value": 154.0,
                    "recorded_at": "2026-01-01T00:00:00Z",
                },
            ],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["indication"] == "diabetes"
        assert data["model_id"] == "wysh.synthetic.diabetes.review.v1"
        assert data["clinical_use_authorized"] is False
        assert data["human_review_required"] is True

    def test_hypertension_disease_workflow(self) -> None:
        response = self.client.post("/v1/disease-intelligence/disease-specific", json={
            "tenant_id": "synthetic-tenant-1",
            "patient_id": "synthetic-patient-1",
            "indication": "hypertension",
            "synthetic": True,
            "facts": [
                {
                    "source_id": "obs-bp-sys-001",
                    "source_type": "observation",
                    "metric": "bp_systolic_mmhg",
                    "value": 155.0,
                    "recorded_at": "2026-01-01T00:00:00Z",
                },
                {
                    "source_id": "obs-bp-dia-001",
                    "source_type": "observation",
                    "metric": "bp_diastolic_mmhg",
                    "value": 95.0,
                    "recorded_at": "2026-01-01T00:00:00Z",
                },
            ],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["indication"] == "hypertension"
        assert data["model_id"] == "wysh.synthetic.hypertension.review.v1"
        assert data["clinical_use_authorized"] is False

    def test_ckd_disease_workflow(self) -> None:
        response = self.client.post("/v1/disease-intelligence/disease-specific", json={
            "tenant_id": "synthetic-tenant-1",
            "patient_id": "synthetic-patient-1",
            "indication": "chronic_kidney_disease",
            "synthetic": True,
            "facts": [
                {
                    "source_id": "obs-egfr-001",
                    "source_type": "observation",
                    "metric": "egfr_ml_min_1_73m2",
                    "value": 45.0,
                    "recorded_at": "2026-01-01T00:00:00Z",
                },
                {
                    "source_id": "obs-uacr-001",
                    "source_type": "observation",
                    "metric": "urine_albumin",
                    "value": 45.0,
                    "recorded_at": "2026-01-01T00:00:00Z",
                },
            ],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["indication"] == "chronic_kidney_disease"
        assert data["model_id"] == "wysh.synthetic.ckd.review.v1"
        assert data["clinical_use_authorized"] is False

    def test_unknown_indication_returns_error(self) -> None:
        response = self.client.post("/v1/disease-intelligence/disease-specific", json={
            "tenant_id": "synthetic-tenant-1",
            "patient_id": "synthetic-patient-1",
            "indication": "nonexistent_disease",
            "synthetic": True,
            "facts": [],
        })
        assert response.status_code == 400


class TestSecurityBoundaries:
    """Security boundary tests ensuring synthetic-only and deny-by-default."""

    def setup_method(self) -> None:
        self.client = TestClient(create_app(Settings()))

    def test_real_patient_identifiers_are_rejected(self) -> None:
        response = self.client.post("/v1/snapshots", json={
            "tenant_id": "real-hospital-tenant",
            "patient_id": "real-patient-12345",
            "synthetic": True,
        })
        assert response.status_code == 400

    def test_phi_in_context_is_rejected(self) -> None:
        response = self.client.post("/v1/snapshots", json={
            "tenant_id": "synthetic-tenant-1",
            "patient_id": "synthetic-patient-1",
            "synthetic": True,
            "context": {
                "mrn": "MRN-123456",
                "name": "John Doe",
                "phone": "555-1234",
            },
        })
        assert response.status_code == 400

    def test_phi_in_observation_source_id_is_rejected(self) -> None:
        response = self.client.post("/v1/snapshots", json={
            "tenant_id": "synthetic-tenant-1",
            "patient_id": "synthetic-patient-1",
            "synthetic": True,
            "facts": [
                {
                    "source_id": "patient-MRN-12345",
                    "source_type": "observation",
                    "metric": "hba1c_percent",
                    "value": 7.2,
                    "recorded_at": "2026-01-01T00:00:00Z",
                },
            ],
        })
        assert response.status_code == 400


class TestAPIVersioning:
    """API versioning tests."""

    def setup_method(self) -> None:
        self.client = TestClient(create_app(Settings()))

    def test_api_v1_prefix_is_used(self) -> None:
        response = self.client.post("/v1/snapshots", json={
            "tenant_id": "synthetic-tenant-1",
            "patient_id": "synthetic-patient-1",
            "synthetic": True,
        })
        assert response.status_code == 200

    def test_unknown_endpoint_returns_404(self) -> None:
        response = self.client.get("/v1/nonexistent-endpoint")
        assert response.status_code == 404