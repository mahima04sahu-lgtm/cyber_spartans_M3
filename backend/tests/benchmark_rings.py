"""
Latency Benchmark Suite for Syndicate Ring & Temporal Window Endpoints.
"""

import time
import duckdb
import numpy as np
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db import init_db

init_db("abhedya/data/db/abhedya.duckdb")
client = TestClient(app)

print("=== LATENCY BENCHMARK: Syndicate Ring & Export Endpoints ===")

# Test accounts
sample_accs = ["910000000001", "910000000002", "910000000003", "910000000004", "910000000005"]

endpoints = [
    ("/api/rings?limit=20", "List Detected Rings"),
    (f"/api/ring/{sample_accs[0]}", "Syndicate Ring Extraction"),
    (f"/api/ring/{sample_accs[0]}/export?format=csv", "Stream Ring Transactions CSV"),
    (f"/api/graph/window?accounts={','.join(sample_accs[:3])}&from_ts=2026-09-01 00:00:00", "Temporal Window Filter"),
]

for ep, name in endpoints:
    latencies = []
    for _ in range(20):
        t0 = time.time()
        res = client.get(ep)
        latencies.append((time.time() - t0) * 1000)
    
    p50 = np.percentile(latencies, 50)
    p95 = np.percentile(latencies, 95)
    print(f"  {name:<32} | p50: {p50:6.2f} ms | p95: {p95:6.2f} ms | Status: {res.status_code}")
