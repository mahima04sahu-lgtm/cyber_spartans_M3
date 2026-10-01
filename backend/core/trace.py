"""
High-Performance In-Memory CSR Graph Tracing Engine for Abhedya-Chakra.
Builds zero-copy NumPy CSR adjacency structures from DuckDB and executes
temporally-constrained multi-hop money flow tracing in < 50ms.
"""

from collections import deque
import os
import time
from typing import Dict, Any, List, Optional, Set, Tuple
import duckdb
import numpy as np


class CSRGraph:
    """
    Compact In-Memory Compressed Sparse Row (CSR) graph representation.
    """
    def __init__(self):
        self.num_nodes: int = 0
        self.num_edges: int = 0
        self.indptr: np.ndarray = np.array([], dtype=np.int32)
        self.receivers: np.ndarray = np.array([], dtype=np.int32)
        self.timestamps: np.ndarray = np.array([], dtype=np.int64)
        self.amounts: np.ndarray = np.array([], dtype=np.float64)
        self.txn_row_ids: np.ndarray = np.array([], dtype=np.int64)
        
        self.acc_to_id: Dict[str, int] = {}
        self.id_to_acc: List[str] = []

    @classmethod
    def from_duckdb(cls, con: duckdb.DuckDBPyConnection) -> "CSRGraph":
        """Build CSR graph directly from DuckDB tables using zero-copy NumPy extraction."""
        t0 = time.time()
        graph = cls()

        # 1. Load Node Mappings
        acc_df = con.execute("SELECT account_str, account_id FROM accounts ORDER BY account_id").fetchdf()
        graph.num_nodes = len(acc_df)
        graph.id_to_acc = acc_df["account_str"].tolist()
        graph.acc_to_id = {acc: idx for idx, acc in enumerate(graph.id_to_acc)}

        # 2. Fetch all edges sorted by sender_id, epoch_sec
        edges_df = con.execute("""
            SELECT 
                txn_row_id, sender_id, receiver_id, epoch_sec, amount
            FROM txn_int
            ORDER BY sender_id, epoch_sec;
        """).fetchdf()
        
        graph.num_edges = len(edges_df)

        if graph.num_edges == 0:
            graph.indptr = np.zeros(graph.num_nodes + 1, dtype=np.int32)
            graph.receivers = np.array([], dtype=np.int32)
            graph.timestamps = np.array([], dtype=np.int64)
            graph.amounts = np.array([], dtype=np.float64)
            graph.txn_row_ids = np.array([], dtype=np.int64)
            return graph

        # Zero-copy extraction to NumPy arrays
        senders = edges_df["sender_id"].to_numpy(dtype=np.int32)
        graph.receivers = edges_df["receiver_id"].to_numpy(dtype=np.int32)
        graph.timestamps = edges_df["epoch_sec"].to_numpy(dtype=np.int64)
        graph.amounts = edges_df["amount"].to_numpy(dtype=np.float64)
        graph.txn_row_ids = edges_df["txn_row_id"].to_numpy(dtype=np.int64)

        # Build indptr array via vectorized bincount & cumsum
        indptr = np.zeros(graph.num_nodes + 1, dtype=np.int32)
        counts = np.bincount(senders, minlength=graph.num_nodes)
        indptr[1:] = np.cumsum(counts)
        graph.indptr = indptr

        dur = time.time() - t0
        print(f"CSR Graph Built: {graph.num_nodes:,} nodes, {graph.num_edges:,} edges in {dur:.3f}s")
        return graph


# Global graph singleton instance
_GRAPH_INSTANCE: Optional[CSRGraph] = None


def get_graph(con: Optional[duckdb.DuckDBPyConnection] = None) -> CSRGraph:
    """Get or build global CSR Graph instance."""
    global _GRAPH_INSTANCE
    if _GRAPH_INSTANCE is None:
        if con is None:
            from backend.app.db import get_db
            con = get_db()
        _GRAPH_INSTANCE = CSRGraph.from_duckdb(con)
    return _GRAPH_INSTANCE


def reset_graph():
    """Reset global graph cache."""
    global _GRAPH_INSTANCE
    _GRAPH_INSTANCE = None


def trace_money_flow(
    con: duckdb.DuckDBPyConnection,
    victim_account: str,
    max_hops: int = 4,
    strict_mode: bool = False,
    max_dwell_hours: float = 24.0,
    max_edges_cap: int = 5000,
) -> Dict[str, Any]:
    """
    Executes multi-hop downstream money flow tracing from victim_account.
    Enforces Strict Temporal Order: t_out >= t_in AND t_out <= t_in + dwell_window.
    Maintains exact money conservation (forwarded + residual <= received).
    """
    t_start = time.time()
    graph = get_graph(con)

    if victim_account not in graph.acc_to_id:
        return {
            "victim_account": victim_account,
            "found": False,
            "error": f"Victim account '{victim_account}' not found in database.",
            "nodes": [],
            "edges": [],
            "summary": {}
        }

    victim_id = graph.acc_to_id[victim_account]
    dwell_window_sec = int(3600 if strict_mode else max_dwell_hours * 3600)

    # Fetch risk scores and metadata from DuckDB for accounts
    try:
        acc_meta_rows = con.execute("SELECT account_str, risk_score, layer, sender_bank FROM account_scores;").fetchall()
        meta_dict = {r[0]: (float(r[1]), str(r[2]), str(r[3])) for r in acc_meta_rows}
    except Exception:
        meta_dict = {}

    # Node tracking: node_id -> {hop, arrival_time, amount_received, amount_forwarded, residual}
    node_stats: Dict[int, Dict[str, Any]] = {}
    node_stats[victim_id] = {
        "hop": 0,
        "first_arrival_time": 0,
        "amount_received": 0.0,
        "amount_forwarded": 0.0,
        "residual": 0.0,
    }

    queue = deque()

    # Find initial outgoing transfers from victim (Hop 0 -> Hop 1)
    start_idx = graph.indptr[victim_id]
    end_idx = graph.indptr[victim_id + 1]

    if start_idx == end_idx:
        victim_bank = meta_dict.get(victim_account, (0, "Victim", "Unknown Bank"))[2]
        return {
            "victim_account": victim_account,
            "found": True,
            "hops_searched": max_hops,
            "strict_mode": strict_mode,
            "is_truncated": False,
            "execution_time_ms": round((time.time() - t_start) * 1000, 2),
            "message": f"Victim account '{victim_account}' has 0 outgoing transactions.",
            "summary": {
                "total_siphoned": 0.0,
                "nodes_in_trail": 1,
                "edges_in_trail": 0,
                "l1_total_amount": 0.0,
                "l2_total_amount": 0.0,
                "l3_total_amount": 0.0,
                "holding_accounts": [],
                "terminal_cashout_accounts": [],
            },
            "nodes": [{
                "account": victim_account,
                "hop": 0,
                "first_arrival_time": "N/A",
                "amount_received": 0.0,
                "amount_forwarded": 0.0,
                "residual_balance": 0.0,
                "mule_risk_score": 0.0,
                "layer": "Victim",
                "bank_name": victim_bank,
            }],
            "edges": [],
        }

    initial_outgoing_amount = 0.0
    for idx in range(start_idx, end_idx):
        rec_id = graph.receivers[idx]
        ts_ep = graph.timestamps[idx]
        amt = graph.amounts[idx]
        
        initial_outgoing_amount += amt
        queue.append((rec_id, 1, ts_ep, amt, idx, victim_id))

    node_stats[victim_id]["amount_forwarded"] = initial_outgoing_amount

    traced_edges: List[Dict[str, Any]] = []
    visited_edges: Set[int] = set()
    is_truncated = False

    # BFS Traversal
    while queue and len(traced_edges) < max_edges_cap:
        curr_id, hop, arrival_time, inbound_amt, edge_idx, sender_id = queue.popleft()

        if edge_idx in visited_edges:
            continue
        visited_edges.add(edge_idx)

        # Record/update target node stats
        if curr_id not in node_stats:
            node_stats[curr_id] = {
                "hop": hop,
                "first_arrival_time": arrival_time,
                "amount_received": 0.0,
                "amount_forwarded": 0.0,
                "residual": 0.0,
            }
        else:
            node_stats[curr_id]["hop"] = min(node_stats[curr_id]["hop"], hop)
            if node_stats[curr_id]["first_arrival_time"] == 0 or arrival_time < node_stats[curr_id]["first_arrival_time"]:
                node_stats[curr_id]["first_arrival_time"] = arrival_time

        node_stats[curr_id]["amount_received"] += inbound_amt

        sender_acc_str = graph.id_to_acc[sender_id]
        receiver_acc_str = graph.id_to_acc[curr_id]
        txn_row_id = graph.txn_row_ids[edge_idx]

        traced_edges.append({
            "txn_id": f"TXN_{txn_row_id}",
            "sender_account": sender_acc_str,
            "receiver_account": receiver_acc_str,
            "amount": round(inbound_amt, 2),
            "traced_amount": round(inbound_amt, 2),
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(arrival_time)),
            "epoch_sec": int(arrival_time),
            "payment_mode": "UPI",
            "hop": hop,
        })

        # Forward downstream if hop < max_hops
        if hop < max_hops:
            out_start = graph.indptr[curr_id]
            out_end = graph.indptr[curr_id + 1]

            valid_out_indices = []
            for o_idx in range(out_start, out_end):
                o_ts = graph.timestamps[o_idx]
                if o_ts >= arrival_time and o_ts <= arrival_time + dwell_window_sec:
                    valid_out_indices.append(o_idx)

            if valid_out_indices:
                total_out_vol = sum(graph.amounts[idx] for idx in valid_out_indices)
                forward_cap = min(inbound_amt, total_out_vol)
                node_stats[curr_id]["amount_forwarded"] += forward_cap

                for o_idx in valid_out_indices:
                    next_rec_id = graph.receivers[o_idx]
                    o_ts = graph.timestamps[o_idx]
                    o_amt = graph.amounts[o_idx]
                    
                    allocated_amt = (o_amt / total_out_vol) * forward_cap if total_out_vol > 0 else 0.0

                    if len(traced_edges) >= max_edges_cap:
                        is_truncated = True
                        break

                    queue.append((next_rec_id, hop + 1, o_ts, allocated_amt, o_idx, curr_id))

    if len(traced_edges) >= max_edges_cap:
        is_truncated = True

    # Compute Residual Balances for nodes
    for nid, stats in node_stats.items():
        stats["residual"] = max(0.0, round(stats["amount_received"] - stats["amount_forwarded"], 2))
        stats["amount_received"] = round(stats["amount_received"], 2)
        stats["amount_forwarded"] = round(stats["amount_forwarded"], 2)

    # Format Node List
    nodes_list = []
    l1_total = 0.0
    l2_total = 0.0
    l3_total = 0.0
    holding_accounts = []
    terminal_cashout_accounts = []

    for nid, stats in node_stats.items():
        acc_str = graph.id_to_acc[nid]
        score, layer, bank = meta_dict.get(acc_str, (0.0, "none", "Bank"))

        if stats["hop"] == 1:
            layer = "L1"
            l1_total += stats["amount_received"]
        elif stats["hop"] == 2:
            layer = "L2"
            l2_total += stats["amount_received"]
        elif stats["hop"] >= 3:
            layer = "L3" if layer == "none" else layer
            l3_total += stats["amount_received"]

        if stats["residual"] > 0 and nid != victim_id:
            holding_accounts.append({
                "account": acc_str,
                "residual_balance": stats["residual"],
                "layer": layer,
                "risk_score": score
            })

        if layer == "L3" or (stats["hop"] >= 2 and stats["amount_forwarded"] == 0):
            terminal_cashout_accounts.append({
                "account": acc_str,
                "amount_held": stats["residual"],
                "layer": layer,
                "risk_score": score
            })

        first_ts_str = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(stats["first_arrival_time"])) if stats["first_arrival_time"] > 0 else "N/A"

        nodes_list.append({
            "account": acc_str,
            "hop": stats["hop"],
            "first_arrival_time": first_ts_str,
            "amount_received": stats["amount_received"],
            "amount_forwarded": stats["amount_forwarded"],
            "residual_balance": stats["residual"],
            "mule_risk_score": score,
            "layer": layer,
            "bank_name": bank,
        })

    duration_ms = round((time.time() - t_start) * 1000, 2)

    return {
        "victim_account": victim_account,
        "found": True,
        "hops_searched": max_hops,
        "strict_mode": strict_mode,
        "is_truncated": is_truncated,
        "execution_time_ms": duration_ms,
        "summary": {
            "total_siphoned": round(initial_outgoing_amount, 2),
            "nodes_in_trail": len(nodes_list),
            "edges_in_trail": len(traced_edges),
            "l1_total_amount": round(l1_total, 2),
            "l2_total_amount": round(l2_total, 2),
            "l3_total_amount": round(l3_total, 2),
            "holding_accounts": holding_accounts,
            "terminal_cashout_accounts": terminal_cashout_accounts,
        },
        "nodes": nodes_list,
        "edges": traced_edges,
    }


def suggest_auto_detected_victims(con: duckdb.DuckDBPyConnection, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Auto-detects victim account candidates: accounts sending large transfers
    to high-risk mule accounts (L1/L2).
    """
    query = """
        SELECT 
            t.sender_acc AS victim_account,
            t.sender_bank AS bank_name,
            COUNT(DISTINCT t.receiver_acc) AS mule_targets_count,
            SUM(t.amount) AS total_stolen_amount,
            strftime(MIN(t.ts), '%Y-%m-%d %H:%M:%S') AS first_loss,
            strftime(MAX(t.ts), '%Y-%m-%d %H:%M:%S') AS last_loss
        FROM txn t
        JOIN mule_risk m ON t.receiver_acc = m.account_str
        WHERE m.risk_score >= 40.0 AND m.layer IN ('L1', 'L2', 'L3')
        GROUP BY t.sender_acc, t.sender_bank
        ORDER BY total_stolen_amount DESC
        LIMIT $1;
    """
    try:
        rows = con.execute(query, [limit]).fetchall()
        return [
            {
                "victim_account": r[0],
                "bank_name": r[1],
                "mule_targets_count": r[2],
                "total_stolen_amount": round(float(r[3]), 2),
                "first_loss": r[4],
                "last_loss": r[5],
            }
            for r in rows
        ]
    except Exception:
        return []
