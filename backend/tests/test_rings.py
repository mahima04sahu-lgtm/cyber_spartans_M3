"""
Unit tests for Syndicate Ring isolation, Streaming Exporter, & Temporal Window APIs.
"""

import os
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db import init_db, close_db, get_db

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


def get_test_account():
    con = get_db()
    row = con.execute("SELECT sender_acc FROM txn LIMIT 1").fetchone()
    return row[0] if row else "HDFC10000336"


def test_get_syndicate_ring():
    account_id = get_test_account()
    response = client.get(f"/api/ring/{account_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["found"] == True
    assert "summary" in data
    assert "nodes" in data
    assert "edges" in data
    assert data["summary"]["ring_size"] >= 1


def test_export_ring_transactions_csv():
    account_id = get_test_account()
    response = client.get(f"/api/ring/{account_id}/export?format=csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment; filename=" in response.headers["content-disposition"]
    lines = response.text.splitlines()
    assert len(lines) >= 1
    assert "Transaction_ID,Sender_Account" in lines[0]


def test_export_ring_transactions_json():
    account_id = get_test_account()
    response = client.get(f"/api/ring/{account_id}/export?format=json")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data


def test_graph_temporal_window():
    account_id = get_test_account()
    response = client.get(f"/api/graph/window?accounts={account_id}&from_ts=2026-09-01 00:00:00")
    assert response.status_code == 200
    data = response.json()
    assert "edges" in data
    assert isinstance(data["edges"], list)


def test_list_detected_rings():
    response = client.get("/api/rings?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "rings" in data
    assert isinstance(data["rings"], list)
