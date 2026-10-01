"""
Latency Benchmark Suite for In-Memory Graph Tracing Engine.
Runs 100 random victim traces on 2M dataset and reports p50, p90, and p95 latencies.
"""

import time
import duckdb
import numpy as np

from backend.core.trace import trace_money_flow, reset_graph, get_graph


def run_benchmark(db_path: str = "abhedya/data/db/abhedya.duckdb", num_samples: int = 100):
    print(f"=== LATENCY BENCHMARK: 4-Hop Graph Tracing ({num_samples} Random Victims) ===")
    con = duckdb.connect(db_path, read_only=True)

    # 1. Warm up graph initialization
    t0 = time.time()
    get_graph(con)
    init_dur = (time.time() - t0) * 1000
    print(f"CSR Graph In-Memory Init Time: {init_dur:.2f} ms")

    # 2. Select random victim/sender accounts from dataset
    victim_rows = con.execute("""
        SELECT DISTINCT victim_account FROM (
            SELECT sender_acc AS victim_account FROM txn
        ) LIMIT 500;
    """).fetchall()

    victim_pool = [r[0] for r in victim_rows]
    sample_victims = np.random.choice(victim_pool, size=min(num_samples, len(victim_pool)), replace=False)

    latencies_ms = []

    for v in sample_victims:
        t_start = time.time()
        res = trace_money_flow(con, victim_account=v, max_hops=4, strict_mode=False)
        dur_ms = (time.time() - t_start) * 1000
        latencies_ms.append(dur_ms)

    con.close()

    p50 = np.percentile(latencies_ms, 50)
    p90 = np.percentile(latencies_ms, 90)
    p95 = np.percentile(latencies_ms, 95)
    max_lat = np.max(latencies_ms)
    avg_lat = np.mean(latencies_ms)

    print("\n================ GRAPH TRACING BENCHMARK RESULTS ================")
    print(f"  Sample Count      : {len(latencies_ms)} queries")
    print(f"  Average Latency   : {avg_lat:6.2f} ms")
    print(f"  p50 Latency       : {p50:6.2f} ms")
    print(f"  p90 Latency       : {p90:6.2f} ms")
    print(f"  p95 Latency       : {p95:6.2f} ms  (Target: < 2,000 ms / Goal < 300 ms)")
    print(f"  Max Latency       : {max_lat:6.2f} ms")
    print("=================================================================\n")

    return {
        "p50": p50,
        "p90": p90,
        "p95": p95,
        "max": max_lat,
        "avg": avg_lat
    }


if __name__ == "__main__":
    run_benchmark()
