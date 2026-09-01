from __future__ import annotations

import time
import tracemalloc

from app.duration_prediction.runtime import DurationPredictionProvider
from backend.tests.p6_duration_runtime_support import (
    build_test_provider,
    canonical_json_bytes,
    runtime_requests,
)


def _nearest_rank(values: list[int], numerator: int, denominator: int) -> int:
    ordered = sorted(values)
    rank = (numerator * len(ordered) + denominator - 1) // denominator
    return ordered[rank - 1]


def test_development_runtime_latency_and_memory_profile_is_bounded() -> None:
    provider: DurationPredictionProvider = build_test_provider()
    requests = runtime_requests()
    for index in range(provider.policy.benchmark_warmup_calls):
        provider.predict(requests[index % len(requests)])

    latencies: list[int] = []
    tracemalloc.start()
    try:
        for index in range(provider.policy.benchmark_measured_calls):
            started = time.perf_counter_ns()
            prediction = provider.predict(requests[index % len(requests)])
            latencies.append(time.perf_counter_ns() - started)
            assert prediction["fallback_reason"] == "NONE"
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    p95_latency_ns = _nearest_rank(latencies, 95, 100)
    assert len(latencies) == 256
    assert p95_latency_ns <= provider.policy.max_p95_latency_ns
    assert peak_bytes <= provider.policy.max_peak_allocated_bytes


def test_prediction_bytes_stay_below_explicit_resource_limit() -> None:
    provider = build_test_provider()

    sizes = [
        len(canonical_json_bytes(provider.predict(request)))
        for request in runtime_requests()
    ]

    assert max(sizes) < provider.policy.max_prediction_bytes
    assert min(sizes) > 0
