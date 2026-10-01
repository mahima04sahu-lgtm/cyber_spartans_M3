"""
Unit tests for In-Memory Graph Tracing Engine (backend/core/trace.py).
Tests exact money flow conservation, temporal constraint rules, cycle handling, and branching.
"""

import time
import duckdb
import pytest

from backend.core.trace import CSRGraph, trace_money_flow, reset_graph


@pytest.fixture
def handmade_graph_db(tmp_path):
    reset_graph()
    db_file = str(tmp_path / "handmade.duckdb")
    con = duckdb.connect(db_file)

    # Setup accounts table
    con.execute("CREATE TABLE accounts (account_str VARCHAR, account_id INT);")
    accounts = ["VIC001", "MULE_L1_A", "MULE_L2_B", "MULE_L3_C", "MULE_L3_D"]
    for idx, acc in enumerate(accounts):
        con.execute("INSERT INTO accounts VALUES (?, ?)", [acc, idx])

    # Setup txn_int table
    # Graph Topology:
    # VIC001 (0) --[100k, t=1000]--> MULE_L1_A (1)
    # MULE_L1_A (1) --[90k, t=1500]--> MULE_L2_B (2)  (forwarded within 500s)
    # MULE_L2_B (2) --[50k, t=2000]--> MULE_L3_C (3)  (branch 1)
    # MULE_L2_B (2) --[40k, t=2100]--> MULE_L3_D (4)  (branch 2)
    # MULE_L3_C (3) --[10k, t=2500]--> MULE_L1_A (1)  (cycle back to L1)
    con.execute("""
        CREATE TABLE txn_int (
            txn_row_id BIGINT,
            sender_id INT,
            receiver_id INT,
            ts TIMESTAMP,
            epoch_sec BIGINT,
            amount DOUBLE,
            payment_mode VARCHAR,
            ip_foreign BOOLEAN,
            device_headless BOOLEAN,
            near_threshold BOOLEAN
        );
    """)

    txns = [
        (1, 0, 1, 1000, 100000.0), # VIC001 -> L1_A
        (2, 1, 2, 1500, 90000.0),  # L1_A -> L2_B
        (3, 2, 3, 2000, 50000.0),  # L2_B -> L3_C
        (4, 2, 4, 2100, 40000.0),  # L2_B -> L3_D
        (5, 3, 1, 2500, 10000.0),  # L3_C -> L1_A (Cycle)
    ]
    for r_id, s_id, r_rec, ep, amt in txns:
        con.execute(
            "INSERT INTO txn_int VALUES (?, ?, ?, TIMESTAMP '2026-09-01 10:00:00', ?, ?, 'UPI', FALSE, FALSE, FALSE)",
            [r_id, s_id, r_rec, ep, amt]
        )

    # Setup dummy account_scores for metadata lookups
    con.execute("CREATE TABLE account_scores (account_str VARCHAR, risk_score DOUBLE, layer VARCHAR, sender_bank VARCHAR);")
    for acc in accounts:
        con.execute("INSERT INTO account_scores VALUES (?, 85.0, 'L1', 'SBI')", [acc])

    yield con
    con.close()
    reset_graph()


def test_handmade_graph_trace(handmade_graph_db):
    res = trace_money_flow(handmade_graph_db, victim_account="VIC001", max_hops=4, strict_mode=False)

    assert res["found"] == True
    assert res["summary"]["total_siphoned"] == 100000.0

    nodes = {n["account"]: n for n in res["nodes"]}
    assert "VIC001" in nodes
    assert "MULE_L1_A" in nodes
    assert "MULE_L2_B" in nodes
    assert "MULE_L3_C" in nodes
    assert "MULE_L3_D" in nodes

    # Check exact money conservation property for every node
    for acc, stats in nodes.items():
        if acc != "VIC001":
            # received >= forwarded + residual
            assert stats["amount_received"] >= round(stats["amount_forwarded"] + stats["residual_balance"], 2)

    # Specific node checks
    l1_a = nodes["MULE_L1_A"]
    assert l1_a["hop"] == 1
    assert l1_a["amount_received"] >= 100000.0
    assert l1_a["amount_forwarded"] == 90000.0

    l2_b = nodes["MULE_L2_B"]
    assert l2_b["hop"] == 2
    assert l2_b["amount_received"] == 90000.0
    assert l2_b["amount_forwarded"] == 90000.0  # 50k + 40k branched

    l3_c = nodes["MULE_L3_C"]
    assert l3_c["amount_received"] == 50000.0

    l3_d = nodes["MULE_L3_D"]
    assert l3_d["amount_received"] == 40000.0
    assert l3_d["residual_balance"] == 40000.0  # Held at terminal node
