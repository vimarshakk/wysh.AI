from __future__ import annotations

from collections import Counter
from threading import Lock
from typing import Final


_PROVIDER_NAMES: Final = frozenset({"gemini", "medgemma", "openai-compatible", "vllm", "llama.cpp"})
_LATENCY_BUCKETS_MS: Final = (50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000)


class Metrics:
    """Small dependency-free metrics sink with deliberately bounded cardinality."""

    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._lock = Lock()

    def inc(self, event: str, amount: int = 1) -> None:
        with self._lock:
            self._counts[event] += amount

    def observe_provider(self, provider: str, status: str, latency_ms: int) -> None:
        """Record bounded provider-route telemetry without request content."""
        if provider not in _PROVIDER_NAMES:
            provider = "unknown"
        if status not in {"success", "failure"}:
            status = "failure"
        latency_ms = max(0, int(latency_ms))
        with self._lock:
            self._counts[f"provider_route_{status}_{provider}"] += 1
            for bucket in _LATENCY_BUCKETS_MS:
                if latency_ms <= bucket:
                    self._counts[f"provider_route_latency_ms_bucket_{provider}_{bucket}"] += 1
            self._counts[f"provider_route_latency_ms_count_{provider}"] += 1
            self._counts[f"provider_route_latency_ms_sum_{provider}"] += latency_ms

    def render(self) -> str:
        with self._lock:
            values = dict(self._counts)
        lines = [
            "# HELP wysh_ai_events_total Internal low-cardinality wysh.AI events.",
            "# TYPE wysh_ai_events_total counter",
        ]
        for event, value in sorted(values.items()):
            safe_event = event.replace('"', "'")
            lines.append(f'wysh_ai_events_total{{event="{safe_event}"}} {value}')
        return "\n".join(lines) + "\n"
