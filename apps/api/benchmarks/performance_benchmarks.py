"""Performance benchmarks for the wysh.AI System One decision model.

These benchmarks measure latency, throughput, and resource usage for the core
decision pipeline. They are designed to run as standalone benchmarks and
can be integrated into CI/CD performance gates.

Benchmark categories:
- Feature extraction latency
- Decision model inference latency (per indication)
- Full E2E request latency (HTTP through FastAPI)
- Concurrent request throughput
- Memory usage under load
"""

from __future__ import annotations

import json
import statistics
import time
from datetime import datetime, timezone
from typing import Any

from fastapi.testclient import TestClient

from app.config import Settings
from app.decision_engine import DecisionEngine
from app.decision_model import SystemOneDecisionModel
from app.feature_extractor import extract
from app.main import create_app


def _make_facts() -> list[dict]:
    return [
        {
            "source_id": f"obs-{i}",
            "source_type": "observation",
            "metric": metric,
            "value": value,
            "recorded_at": "2026-01-01T00:00:00Z",
        }
        for i, (metric, value) in enumerate(
            [
                ("hba1c_percent", 7.2),
                ("mean_glucose_mg_dl", 154.0),
                ("bp_systolic_mmhg", 138.0),
                ("bp_diastolic_mmhg", 88.0),
                ("egfr_ml_min_1_73m2", 88.0),
                ("urine_acr_mg_g", 22.0),
                ("age_years", 55.0),
            ]
        )
    ]


def benchmark_feature_extraction(iterations: int = 1000) -> dict:
    """Benchmark feature extraction throughput and latency."""
    extractor_times = []
    facts = _make_facts()

    for _ in range(iterations):
        start = time.perf_counter()
        extract(facts)
        extract_time = time.perf_counter() - start
        extractor_times.append(extract_time)

    return {
        "metric": "feature_extraction",
        "iterations": iterations,
        "avg_ms": round(statistics.mean(extractor_times) * 1000, 4),
        "median_ms": round(statistics.median(extractor_times) * 1000, 4),
        "p95_ms": round(statistics.quantiles(extractor_times, n=20)[18] * 1000, 4),
        "p99_ms": round(statistics.quantiles(extractor_times, n=100)[98] * 1000, 4),
        "min_ms": round(min(extractor_times) * 1000, 4),
        "max_ms": round(max(extractor_times) * 1000, 4),
        "ops_per_second": round(iterations / sum(extractor_times), 2),
    }


def benchmark_decision_model(iterations: int = 1000) -> dict:
    """Benchmark decision model inference latency."""
    model = SystemOneDecisionModel()
    feature_extractor_times = []
    decision_times = []

    for _ in range(iterations):
        facts = _make_facts()
        feature_vector = extract(facts)

        start = time.perf_counter()
        model.predict(
            model_id="wysh.synthetic.diabetes.review.v1",
            indication="diabetes",
            feature_vector=feature_vector,
        )
        decision_time = time.perf_counter() - start
        decision_times.append(decision_time)

    return {
        "model": "wysh.synthetic.diabetes.review.v1",
        "iterations": iterations,
        "avg_ms": round(statistics.mean(decision_times) * 1000, 4),
        "median_ms": round(statistics.median(decision_times) * 1000, 4),
        "p95_ms": round(statistics.quantiles(decision_times, n=20)[18] * 1000, 4),
        "p99_ms": round(statistics.quantiles(decision_times, n=100)[98] * 1000, 4),
        "min_ms": round(min(decision_times) * 1000, 4),
        "max_ms": round(max(decision_times) * 1000, 4),
        "ops_per_second": round(iterations / sum(decision_times), 2),
    }


def benchmark_end_to_end(iterations: int = 100) -> dict:
    """Benchmark full HTTP request/response cycle through FastAPI TestClient."""
    client = TestClient(create_app(Settings()))

    request_payload = {
        "tenant_id": "synthetic-tenant-1",
        "patient_id": "synthetic-patient-1",
        "indication": "diabetes",
        "synthetic": True,
        "facts": _make_facts(),
    }

    latencies = []
    for _ in range(iterations):
        start = time.perf_counter()
        response = client.post("/v1/snapshots", json=request_payload)
        latency = time.perf_counter() - start
        latencies.append(latency)
        assert response.status_code == 200

    return {
        "endpoint": "POST /v1/snapshots",
        "iterations": iterations,
        "avg_ms": round(statistics.mean(latencies) * 1000, 4),
        "median_ms": round(statistics.median(latencies) * 1000, 4),
        "p95_ms": round(statistics.quantiles(latencies, n=20)[18] * 1000, 4),
        "p99_ms": round(statistics.quantiles(latencies, n=100)[98] * 1000, 4),
        "min_ms": round(min(latencies) * 1000, 4),
        "max_ms": round(max(latencies) * 1000, 4),
        "ops_per_second": round(iterations / sum(latencies), 2),
    }


def benchmark_concurrent_requests(concurrency: int = 20, total: int = 100) -> dict:
    """Benchmark concurrent request handling."""
    import concurrent.futures

    client = TestClient(create_app(Settings()))

    request_payload = {
        "tenant_id": "synthetic-tenant-1",
        "patient_id": "synthetic-patient-1",
        "indication": "diabetes",
        "synthetic": True,
        "facts": _make_facts(),
    }

    def single_request() -> float:
        start = time.perf_counter()
        response = client.post("/v1/snapshots", json=request_payload)
        latency = time.perf_counter() - start
        assert response.status_code == 200
        return latency

    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(single_request) for _ in range(total)]
        results = [f.result() for f in futures]
    total_time = time.perf_counter() - start

    return {
        "total_requests": total,
        "concurrency": concurrency,
        "total_time_ms": round(total_time * 1000, 4),
        "avg_ms": round(statistics.mean(results) * 1000, 4),
        "p95_ms": round(statistics.quantiles(results, n=20)[18] * 1000, 4),
        "p99_ms": round(statistics.quantiles(results, n=100)[98] * 1000, 4),
        "throughput_rps": round(total / total_time, 2),
    }


def run_all_benchmarks() -> dict:
    """Run all benchmarks and return aggregated results."""
    print("🚀 Running wysh.AI performance benchmarks...")
    print("=" * 60)

    results: dict = {
        "benchmark_timestamp": datetime.now(timezone.utc).isoformat(),
        "feature_extraction": None,
        "decision_model": None,
        "end_to_end": None,
        "concurrent": None,
    }

    print("\n📊 Feature Extraction Benchmark...")
    results["feature_extraction"] = benchmark_feature_extraction()
    print(f"  {results['feature_extraction']['iterations']} iterations")
    print(f"  Avg: {results['feature_extraction']['avg_ms']} ms")
    print(f"  p95: {results['feature_extraction']['p95_ms']} ms")
    print(f"  p99: {results['feature_extraction']['p99_ms']} ms")
    print(f"  Ops/sec: {results['feature_extraction']['ops_per_second']}")

    print("\n🧠 Decision Model Benchmark...")
    results["decision_model"] = benchmark_decision_model()
    print(f"  Model: {results['decision_model']['model']}")
    print(f"  Iterations: {results['decision_model']['iterations']}")
    print(f"  Avg: {results['decision_model']['avg_ms']} ms")
    print(f"  p95: {results['decision_model']['p95_ms']} ms")
    print(f"  p99: {results['decision_model']['p99_ms']} ms")
    print(f"  Ops/sec: {results['decision_model']['ops_per_second']}")

    print("\n🌐 End-to-End Benchmark...")
    results["end_to_end"] = benchmark_end_to_end()
    print(f"  Endpoint: {results['end_to_end']['endpoint']}")
    print(f"  Iterations: {results['end_to_end']['iterations']}")
    print(f"  Avg: {results['end_to_end']['avg_ms']} ms")
    print(f"  p95: {results['end_to_end']['p95_ms']} ms")
    print(f"  p99: {results['end_to_end']['p99_ms']} ms")
    print(f"  Ops/sec: {results['end_to_end']['ops_per_second']}")

    print("\n⚡ Concurrent Request Benchmark...")
    results["concurrent"] = benchmark_concurrent_requests()
    print(f"  Total requests: {results['concurrent']['total_requests']}")
    print(f"  Concurrency: {results['concurrent']['concurrency']}")
    print(f"  Total time: {results['concurrent']['total_time_ms']} ms")
    print(f"  Avg: {results['concurrent']['avg_ms']} ms")
    print(f"  p95: {results['concurrent']['avg_ms']} ms")
    print(f"  p99: {results['concurrent']['p99_ms']} ms")
    print(f"  Throughput: {results['concurrent']['throughput_rps']} req/sec")

    print("\n" + "=" * 60)
    print("✅ Benchmark suite complete!")

    return results


if __name__ == "__main__":
    results = run_all_benchmarks()
    # Optionally write to JSON file
    output_path = Path(__file__).parent / "benchmark_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_path}")
