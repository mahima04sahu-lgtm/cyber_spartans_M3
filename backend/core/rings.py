"""
Syndicate Ring Isolation, Temporal Window Filtering, & Streaming Exporter for Abhedya-Chakra.
"""

from io import StringIO
import time
from typing import Dict, Any, List, Optional, Generator
import duckdb


def get_connected_syndicate_ring(con: duckdb.DuckDBPyConnection, seed_account: str, max_depth: int = 3) -> Dict[str, Any]:
    """
    Isolates the connected syndicate ring (connected component) around a suspect account
    using fast index-backed 2-step BFS queries with UNION ALL joins.
    """
    t0 = time.time()
    
    # 1. Step 1: 1st-degree counterparties (UNION ALL for index usage)
    deg1_query = """
        SELECT DISTINCT receiver_acc AS acc FROM txn WHERE sender_acc = $1
        UNION
        SELECT DISTINCT sender_acc AS acc FROM txn WHERE receiver_acc = $1;
    """
    deg1_rows = con.execute(deg1_query, [seed_account]).fetchall()
    if not deg1_rows:
        return {"found": False, "error": f"Account '{seed_account}' not found in transactions."}

    ring_set = {seed_account}
    deg1_accs = [r[0] for r in deg1_rows]
    ring_set.update(deg1_accs)

    # 2. Step 2: 2nd-degree counterparties for high-risk accounts
    con.execute("CREATE OR REPLACE TEMPORARY TABLE deg1_temp AS SELECT unnest($1::VARCHAR[]) AS acc;", [deg1_accs])
    high_risk_deg1 = con.execute("""
        SELECT account_str FROM mule_risk 
        WHERE account_str IN (SELECT acc FROM deg1_temp) AND risk_score >= 40.0;
    """).fetchall()
    
    high_risk_list = [r[0] for r in high_risk_deg1]

    if high_risk_list:
        con.execute("CREATE OR REPLACE TEMPORARY TABLE hr_temp AS SELECT unnest($1::VARCHAR[]) AS acc;", [high_risk_list])
        deg2_query = """
            SELECT DISTINCT acc2 FROM (
                SELECT t.receiver_acc AS acc2 FROM hr_temp h JOIN txn t ON t.sender_acc = h.acc
                UNION ALL
                SELECT t.sender_acc AS acc2 FROM hr_temp h JOIN txn t ON t.receiver_acc = h.acc
            ) LIMIT 300;
        """
        deg2_rows = con.execute(deg2_query).fetchall()
        ring_set.update([r[0] for r in deg2_rows])

    ring_account_list = list(ring_set)[:500]

    # 3. Fetch Nodes details with risk scores & layers
    con.execute("CREATE OR REPLACE TEMPORARY TABLE ring_acc_temp AS SELECT unnest($1::VARCHAR[]) AS account_str;", [ring_account_list])
    
    nodes_detail_query = """
        SELECT 
            r.account_str,
            COALESCE(m.risk_score, 0.0) AS risk_score,
            COALESCE(m.layer, 'none') AS layer,
            COALESCE(m.risk_band, 'Low') AS risk_band,
            COALESCE((SELECT sender_bank FROM txn WHERE sender_acc = r.account_str LIMIT 1), (SELECT receiver_bank FROM txn WHERE receiver_acc = r.account_str LIMIT 1), 'Unknown Bank') AS bank_name,
            COALESCE(f.total_in, 0.0) AS total_in,
            COALESCE(f.total_out, 0.0) AS total_out
        FROM ring_acc_temp r
        LEFT JOIN mule_risk m ON r.account_str = m.account_str
        LEFT JOIN account_features f ON r.account_str = f.account_str;
    """
    node_detail_rows = con.execute(nodes_detail_query).fetchall()
    
    nodes_list = [
        {
            "account": r[0],
            "risk_score": float(r[1]),
            "layer": str(r[2]),
            "risk_band": str(r[3]),
            "bank_name": str(r[4]) if r[4] else "Unknown Bank",
            "total_in": round(float(r[5]), 2) if r[5] else 0.0,
            "total_out": round(float(r[6]), 2) if r[6] else 0.0,
        }
        for r in node_detail_rows
    ]

    # 4. Fetch all intra-ring edges
    edges_query = """
        SELECT 
            t.txn_id, t.sender_acc, t.receiver_acc, t.sender_bank, t.receiver_bank,
            t.amount, strftime(t.ts, '%Y-%m-%d %H:%M:%S') AS ts, t.payment_mode,
            t.narration, t.narration_category, t.ip_address, t.device_type
        FROM txn t
        JOIN ring_acc_temp s ON t.sender_acc = s.account_str
        JOIN ring_acc_temp r ON t.receiver_acc = r.account_str
        ORDER BY t.ts ASC;
    """
    edge_rows = con.execute(edges_query).fetchall()

    edges_list = [
        {
            "txn_id": r[0],
            "sender_account": r[1],
            "receiver_account": r[2],
            "sender_bank": r[3],
            "receiver_bank": r[4],
            "amount": round(float(r[5]), 2),
            "timestamp": r[6],
            "payment_mode": r[7],
            "narration": r[8],
            "narration_category": r[9],
            "ip_address": r[10],
            "device_type": r[11],
        }
        for r in edge_rows
    ]

    # 5. Ring Summary
    total_vol = sum(e["amount"] for e in edges_list)
    banks = list(set(n["bank_name"] for n in nodes_list if n["bank_name"]))
    l1_cnt = sum(1 for n in nodes_list if n["layer"] == "L1")
    l2_cnt = sum(1 for n in nodes_list if n["layer"] == "L2")
    l3_cnt = sum(1 for n in nodes_list if n["layer"] == "L3")
    
    first_ts = edges_list[0]["timestamp"] if edges_list else "N/A"
    last_ts = edges_list[-1]["timestamp"] if edges_list else "N/A"

    duration_ms = round((time.time() - t0) * 1000, 2)

    return {
        "seed_account": seed_account,
        "found": True,
        "execution_time_ms": duration_ms,
        "summary": {
            "ring_size": len(nodes_list),
            "total_edges": len(edges_list),
            "total_volume": round(total_vol, 2),
            "layers_breakdown": {"L1": l1_cnt, "L2": l2_cnt, "L3": l3_cnt},
            "distinct_banks": len(banks),
            "banks_involved": banks[:5],
            "time_span": {"first_seen": first_ts, "last_seen": last_ts},
        },
        "nodes": nodes_list,
        "edges": edges_list,
    }


def stream_ring_transactions_csv(con: duckdb.DuckDBPyConnection, seed_account: str) -> Generator[str, None, None]:
    """
    Streams CSV chunks of all original 11 transaction columns plus mule score/layers
    for a ring using generator iteration (zero large memory lists).
    """
    header = "Transaction_ID,Sender_Account,Receiver_Account,Sender_IFSC,Receiver_IFSC,Amount,Timestamp,Payment_Mode,Narration,IP_Address,Device_Type,Sender_Risk_Score,Receiver_Risk_Score\n"
    yield header

    ring_data = get_connected_syndicate_ring(con, seed_account=seed_account)
    ring_accs = [n["account"] for n in ring_data.get("nodes", [])]

    if not ring_accs:
        return

    con.execute("CREATE OR REPLACE TEMPORARY TABLE stream_ring_temp AS SELECT unnest($1::VARCHAR[]) AS account_str;", [ring_accs])

    query = """
        SELECT 
            t.txn_id, t.sender_acc, t.receiver_acc, t.sender_ifsc, t.receiver_ifsc,
            t.amount, strftime(t.ts, '%Y-%m-%d %H:%M:%S') AS ts, t.payment_mode,
            t.narration, t.ip_address, t.device_type,
            COALESCE(ms.risk_score, 0.0) AS s_score,
            COALESCE(mr.risk_score, 0.0) AS r_score
        FROM txn t
        JOIN stream_ring_temp s ON t.sender_acc = s.account_str
        JOIN stream_ring_temp r ON t.receiver_acc = r.account_str
        LEFT JOIN mule_risk ms ON t.sender_acc = ms.account_str
        LEFT JOIN mule_risk mr ON t.receiver_acc = mr.account_str
        ORDER BY t.ts ASC;
    """
    cursor = con.execute(query)
    
    while True:
        rows = cursor.fetchmany(1000)
        if not rows:
            break
        
        buffer = StringIO()
        for r in rows:
            narr = str(r[8]).replace('"', '""')
            buffer.write(f'{r[0]},{r[1]},{r[2]},{r[3]},{r[4]},{r[5]},{r[6]},{r[7]},"{narr}",{r[9]},{r[10]},{r[11]},{r[12]}\n')
        
        yield buffer.getvalue()


def get_temporal_graph_window(
    con: duckdb.DuckDBPyConnection,
    account_ids: List[str],
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
    limit: int = 1000
) -> List[Dict[str, Any]]:
    """
    Filters transactions for specified accounts within a timestamp window for playback slider.
    """
    con.execute("CREATE OR REPLACE TEMPORARY TABLE win_acc_temp AS SELECT unnest($1::VARCHAR[]) AS account_str;", [account_ids])
    query = """
        SELECT 
            txn_id, sender_acc, receiver_acc, amount, strftime(ts, '%Y-%m-%d %H:%M:%S') AS ts,
            payment_mode, narration_category, ip_foreign, device_headless
        FROM txn
        WHERE (sender_acc IN (SELECT account_str FROM win_acc_temp) OR receiver_acc IN (SELECT account_str FROM win_acc_temp))
          AND ($1 IS NULL OR ts >= TRY_CAST($1 AS TIMESTAMP))
          AND ($2 IS NULL OR ts <= TRY_CAST($2 AS TIMESTAMP))
        ORDER BY ts ASC
        LIMIT $3;
    """
    rows = con.execute(query, [from_ts, to_ts, limit]).fetchall()
    return [
        {
            "txn_id": r[0],
            "sender_account": r[1],
            "receiver_account": r[2],
            "amount": round(float(r[3]), 2),
            "timestamp": r[4],
            "payment_mode": r[5],
            "narration_category": r[6],
            "ip_foreign": bool(r[7]),
            "device_headless": bool(r[8]),
        }
        for r in rows
    ]


def get_detected_syndicate_rings(con: duckdb.DuckDBPyConnection, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Lists detected syndicate rings ranked by total volume and mule risk score.
    """
    query = """
        SELECT 
            m.account_str AS lead_suspect,
            m.layer,
            m.risk_score,
            s.total_in + s.total_out AS total_volume,
            s.distinct_senders + s.distinct_receivers AS connected_degree
        FROM mule_risk m
        JOIN account_scores s ON m.account_str = s.account_str
        WHERE m.risk_score >= 40.0 AND m.layer IN ('L1', 'L2', 'L3')
        ORDER BY m.risk_score DESC, total_volume DESC
        LIMIT $1;
    """
    try:
        rows = con.execute(query, [limit]).fetchall()
        return [
            {
                "ring_id": idx + 1,
                "lead_suspect_account": r[0],
                "layer": r[1],
                "risk_score": float(r[2]),
                "total_volume": round(float(r[3]), 2),
                "connected_degree": int(r[4]),
            }
            for idx, r in enumerate(rows)
        ]
    except Exception:
        return []
