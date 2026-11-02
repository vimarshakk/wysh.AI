"""
System One Performance Benchmark Runner

Runs comprehensive performance benchmarks on the wysh.AI System One decision model.
Includes feature extraction, decision model inference, end-to-end HTTP requests,
and concurrent load testing.

Usage:
    python scripts/run_performance_benchmarks.py
    python scripts/run_performance_benchmarks.py --output benchmarks.json
    python scripts/run_performance_benchmarks.py --iterations 500
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.feature_extractor import extract
from app.decision_model import SystemOneDecisionModel
from app.system_one.decision_model import SystemOneDecisionModel as SysOneDecisionModel

# Reuse existing modules instead of importing from system_one_benchmark which doesn't exist


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
    """Benchmark deterministic feature extraction performance."""
    import time

    extractor_times = []
    facts = _make_facts()

    for _ in range(iterations):
        start = time.perf_counter()
        extract(facts)
        extractor_times.append(time.perf_counter() - start)

    times = extractor_times
    return {
        "metric": "feature_extraction",
        "iterations": iterations,
        "avg_ms": round(statistics.mean(times) * 1000, 4),
        "median_ms": round(statistics.median(times) * 1000, 4),
        "p95_ms": round(statistics.quantiles(times, n=20)[18] * 1000, 4),
        "p99_ms": round(statistics.quantiles(times, n=100)[98] * 1000, 4),
        "min_ms": round(min(times) * 1000, 4),
        "max_ms": round(max(times) * 1000, 4),
        "ops_per_second": round(iterations / sum(times), 2),
    }


def benchmark_decision_model(iterations: int = 1000) -> dict:
    """Benchmark decision model inference latency."""
    model = SystemOneDecisionModel()
    times = []

    for _ in range(iterations):
        facts = _make_facts()
        feature_vector = extract(facts)

        start = time.perf_counter()
        model.predict(
            model_id="wysh.synthetic.diabetes.review.v1",
            indication="diabetes",
            feature_vector=feature_vector,
        )
        decision_times = time.perf_counter() - start
        times.append(decision_time)

    times_list = times
    return {
        "model": "wysh.synthetic.diabetes.review.v1",
        "iterations": iterations,
        "avg_ms": round(statistics.mean(times_list) * 1000, 4),
        "median_ms": round(statistics.median(times_list) * 1000, 4),
        "p95_ms": round(statistics.quantiles(times_list, n=20)[18] * 1000, 4),
        "p99_ms": round(statistics.quantiles(times_list, n=100)[98] * 1000, 4),
        "min_ms": round(min(times_list) * 1000, 4),
        "max_ms": round(max(times_list) * 1000, 4),
        "ops_per_second": round(iterations / sum(times_list), 2),
    }


def benchmark_end_to_end(iterations: int = 100) -> dict:
    """Benchmark full HTTP request/response cycle through FastAPI TestClient."""
    from app.main import create_app
    from app.config import Settings

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

    latencies_list = latencies
    return {
        "endpoint": "POST /v1/snapshots",
        "iterations": iterations,
        "avg_ms": round(statistics.mean(latencies_list) * 1000, 4),
        "median_ms": round(statistics.median(latencies_list) * 1000, 4),
        "p95_ms": round(statistics.quantiles(latencies_list, n=20)[18] * 1000, 4),
        "p99_ms": round(statistics.quantiles(latencies_list, n=100)[98] * 1000, 4),
        "min_ms": round(min(latencies_list) * 1000, 4),
        "max_ms": round(max(latencies_list) * 1000, 4),
        "ops_per_second": round(iterations / sum(latencies_list), 2),
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

    results_list = results
    return {
        "project": "wysh.AI",
        "module": "system_one",
        "component": "decision_engine",
        "test_name": "concurrent_requests",
        "iterations": total,
        "concurrency": concurrency,
        "avg_ms": round(statistics.mean(results_list) * 1000, 4),
        "median_ms": round(statistics.median(results_list) * 1000, 4),
        "p95_ms": round(statistics.quantiles(results_list, n=20)[18] * 1000, 4),
        "p99_ms": round(statistics.quantiles(results_list, n=100)[98] * 1000, 4),
        "min_ms": round(min(results_list) * 1000, 4),
        "max_ms": round(max(results_list) * 1000, 4),
        "total_time_ms": round(total_time * 1000, 4),
        "throughput_rps": round(total / total_time, 2),
    }


def run_all_benchmarks() -> dict:
    """Run all benchmarks and return results."""
    print("Running wysh.AI performance benchmarks...")
    print("=" * 60)

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "feature_extraction": None,
        "decision_model": None,
        "end_to_end": None,
        "concurrent": None,
    }

    print("\nFeature Extraction Benchmark:")
    fe = benchmark_feature_extraction()
    results["feature_extraction"] = fe
    print(f"  Iterations: {fe['iterations']}")
    print(f"  Avg: {fe['avg_ms']} ms")
    print(f"  p95: {fe['p95_ms']} ms")
    print(f"  p99: {fe['p99_ms']} ms")
    print(f"  Ops/sec: {fe['ops_per_second']}")

    print("\nDecision Model Benchmark:")
    dm = benchmark_decision_model()
    results["decision_model"] = dm
    print(f"  Model: {dm['model']}")
    print(f"  Iterations: {dm['iterations']}")
    print(f"  Avg: {dm['avg_ms']} ms")
    print(f"  p95: {dm['p95_ms']} ms")
    print(f"  p99: {dm['p99_ms']} ms")
    print(f"  Ops/sec: {dm['ops_per_second']}")

    print("\nEnd-to-End Benchmark:")
    e2e = benchmark_end_to_end()
    results["end_to_end"] = e2e
    print(f"  Endpoint: {e2e['endpoint']}")
    print(f"  Iterations: {e2e['iterations']}")
    print(f"  Avg: {e2e['avg_ms']} ms")
    print(f"  p95: {e2e['p95_ms']} ms")
    print(f"  p99: {e2e['p99_ms']} ms")
    print(f"  Ops/sec: {e2e['ops_per_second']}")

    print("\nConcurrent Request Benchmark:")
    concurrent = benchmark_concurrent_requests()
    results["concurrent"] = concurrent
    print(f"  Total requests: {concurrent['iterations']}")
    print(f"  Concurrency: {concurrent['concurrency']}")
    print(f"  Total time: {concurrent['total_time_ms']} ms")
    print(f"  Avg: {concurrent['avg_ms']} ms")
    print(f"  p95: {concurrent['p95_ms']} ms")
    print(f"  p99: {concurrent['p99_ms']} ms")
    print(f"  Throughput: {concurrent['throughput_rps']} req/sec")

    print("\n" + "=" * 60)
    print("Benchmark suite complete!")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="wysh.AI System One Performance Benchmark Runner"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path for benchmark results (JSON format)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1000,
        help="Number of iterations for micro-benchmarks (default: 1000)",
    )
    parser.add_argument(
        "--e2e-iterations",
        type=int,
        default=100,
        help="Number of iterations for end-to-end benchmark (default: 100)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=20,
        help="Concurrency level for concurrent request benchmark (default: 20)",
    )
    parser.add_argument(
        "--total-concurrent",
        type=int,
        default=100,
        help="Total concurrent requests (default: 100)",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("wysh.AI System One - Performance Benchmark Suite")
    print("=" * 70)
    print(f"Iterations: {args.iterations}")
    print(f"E2E Iterations: {args.e2e_iterations}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Total Concurrent: {args.total_concurrent}")
    print("=" * 70)

    results = run_all_benchmarks()

    output_path = Path(args.output) if args.output else None
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {output_path}")

    print("\nBenchmark suite complete!")


if __name__ == "__main__":
    main()
