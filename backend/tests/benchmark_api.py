import time
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import init_db

init_db("abhedya/data/db/abhedya.duckdb")
client = TestClient(app)

endpoints = [
    "/health",
    "/api/account/910000000001",
    "/api/account/910000000001/transactions?limit=50",
    "/api/account/910000000001/counterparties",
    "/api/search?q=91000",
    "/api/stats"
]

print("=== FASTAPI API LATENCY BENCHMARK ON 2M DATASET ===")
for ep in endpoints:
    t0 = time.time()
    res = client.get(ep)
    elapsed_ms = (time.time() - t0) * 1000
    status = res.status_code
    proc_time = res.headers.get("X-Process-Time", "N/A")
    print(f"  {ep:<48} | Status: {status} | Latency: {elapsed_ms:6.2f} ms | Server Time: {proc_time}")
