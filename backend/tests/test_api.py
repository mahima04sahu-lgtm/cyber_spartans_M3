"""
Unit tests for FastAPI API endpoints (backend/app/main.py).
"""

import os
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db import init_db, close_db

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    candidates = ["data/db/abhedya.duckdb", "abhedya/data/db/abhedya.duckdb"]
    db_path = None
    for cand in candidates:
        if os.path.exists(cand):
            db_path = cand
            break
            
    if not db_path:
        pytest.skip("Test database abhedya.duckdb does not exist. Run ingestion first.")
    
    init_db(db_path)
    yield
    close_db()


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ok", "degraded"]
    assert "db_connected" in data


def test_get_account_profile():
    # Test valid account number from our generated dataset
    account_id = "910000000001"
    response = client.get(f"/api/account/{account_id}")
    
    if response.status_code == 404:
        # Fallback to any account in DB
        from backend.app.db import get_db
        con = get_db()
        account_id = con.execute("SELECT account_str FROM accounts LIMIT 1").fetchone()[0]
        response = client.get(f"/api/account/{account_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["account_number"] == account_id
    assert "bank_name" in data
    assert "total_received" in data
    assert "total_sent" in data
    assert "top_narrations" in data
    assert "device_summary" in data
    assert "ip_summary" in data


def test_get_account_profile_not_found():
    response = client.get("/api/account/999999999999999")
    assert response.status_code == 404


def test_get_account_transactions():
    account_id = "910000000001"
    response = client.get(f"/api/account/{account_id}/transactions?limit=10&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert data["account_number"] == account_id
    assert "transactions" in data
    assert len(data["transactions"]) <= 10
    if len(data["transactions"]) > 0:
        txn = data["transactions"][0]
        assert "txn_id" in txn
        assert "amount" in txn
        assert "ts" in txn


def test_get_account_counterparties():
    account_id = "910000000001"
    response = client.get(f"/api/account/{account_id}/counterparties")
    assert response.status_code == 200
    data = response.json()
    assert data["account_number"] == account_id
    assert "top_senders" in data
    assert "top_receivers" in data


def test_search_endpoint():
    response = client.get("/api/search?q=9100")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "9100"
    assert "results" in data
    assert isinstance(data["results"], list)


def test_system_stats():
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_transactions"] > 0
    assert data["total_accounts"] > 0
    assert "ingest_benchmark" in data
