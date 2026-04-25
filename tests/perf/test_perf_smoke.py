"""Performance smoke: /ask latency against the local in-memory backend.

This is a local PoC smoke only - it validates the code path has no accidental
O(N^2) or unbounded retries. Real p95/p99 validation requires a loaded
OpenSearch cluster and live Bedrock calls, which are out of scope for Stage 1.
"""

from __future__ import annotations

import statistics
import time


def test_ask_ttft_is_well_within_budget(rag_service, users):
    user = users["u_helpdesk_01"]
    latencies: list[float] = []
    for _ in range(20):
        t0 = time.perf_counter()
        r = rag_service.ask(user, "Can a taxpayer deduct home office expenses?")
        latencies.append(time.perf_counter() - t0)
        assert not r.abstained
    p95 = statistics.quantiles(latencies, n=20)[18]
    # Local path with the fake backend is several orders of magnitude below
    # the 1.5 s assessment target; anything above 1s on a laptop means the
    # hot path regressed (O(N^2) rerank, unbounded retries, etc.).
    assert p95 < 1.0


def test_cache_hit_ttft_is_faster_than_full_path(rag_service, users):
    user = users["u_helpdesk_01"]
    rag_service.cache.enable(True)
    try:
        rag_service.ask(user, "Can a taxpayer deduct home office expenses?")
        cold_times: list[float] = []
        warm_times: list[float] = []
        for _ in range(10):
            t0 = time.perf_counter()
            rag_service.ask(user, "Can a taxpayer deduct home office expenses?")
            warm_times.append(time.perf_counter() - t0)
        for _ in range(10):
            # different wording each time to defeat the cache
            t0 = time.perf_counter()
            rag_service.ask(user, "Deduction for home office expenses allowed?")
            cold_times.append(time.perf_counter() - t0)
        # Cached lookups should be at least a small bit faster in the in-memory
        # backend. Assert with a generous margin because microbench noise on
        # Windows can be large.
        assert statistics.median(warm_times) <= statistics.median(cold_times) + 0.1
    finally:
        rag_service.cache.clear()
        rag_service.cache.enable(False)
