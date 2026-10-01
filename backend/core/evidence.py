"""
Evidence Pack Generator & Cryptographic Hasher for Abhedya-Chakra.
Generates strict JSON Evidence Packs with SHA-256 integrity hashes and placeholder sanitization.
"""

import hashlib
import json
import os
import re
from typing import Dict, Any, List, Tuple
import duckdb


def compute_file_sha256(filepath: str) -> str:
    """Compute SHA-256 hash of a file."""
    if not os.path.exists(filepath):
        return "sha256_dataset_file_not_found"
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def compute_dict_sha256(data: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash of a dictionary."""
    canonical_json = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def build_evidence_pack(
    con: duckdb.DuckDBPyConnection,
    trace_result: Dict[str, Any],
    dataset_path: str = "data/raw/transactions.csv"
) -> Dict[str, Any]:
    """
    Builds a strict, cryptographically hashed JSON evidence pack from a trace result.
    """
    victim_acc = trace_result.get("victim_account", "")
    
    # Query victim bank & IFSC
    victim_bank = "Unknown Bank"
    victim_ifsc = "UNKNOWN000"
    if victim_acc:
        try:
            row = con.execute(
                "SELECT sender_bank, sender_ifsc FROM txn WHERE sender_acc = $1 LIMIT 1",
                [victim_acc]
            ).fetchone()
            if row:
                victim_bank = row[0] or victim_bank
                victim_ifsc = row[1] or victim_ifsc
        except Exception:
            pass

    # Dataset file SHA-256 hash
    dataset_hash = compute_file_sha256(dataset_path)

    # Process Layered Accounts
    layered_accounts = []
    for node in trace_result.get("nodes", []):
        acc = node.get("account", "")
        ifsc = "UNKNOWN000"
        try:
            i_row = con.execute(
                "SELECT sender_ifsc FROM txn WHERE sender_acc = $1 UNION SELECT receiver_ifsc FROM txn WHERE receiver_acc = $1 LIMIT 1",
                [acc]
            ).fetchone()
            if i_row and i_row[0]:
                ifsc = i_row[0]
        except Exception:
            pass

        layered_accounts.append({
            "account": acc,
            "bank": node.get("bank_name", "Unknown Bank"),
            "ifsc": ifsc,
            "layer": node.get("layer", "L1"),
            "first_seen": node.get("first_arrival_time", "N/A"),
            "amount_received": round(float(node.get("amount_received", 0.0)), 2),
            "amount_forwarded": round(float(node.get("amount_forwarded", 0.0)), 2),
            "residual_balance": round(float(node.get("residual_balance", 0.0)), 2),
            "risk_score": float(node.get("mule_risk_score", 0.0)),
        })

    # Process Transactions
    transactions = []
    for edge in trace_result.get("edges", []):
        transactions.append({
            "txn_id": edge.get("txn_id", ""),
            "timestamp": edge.get("timestamp", ""),
            "sender_account": edge.get("sender_account", ""),
            "receiver_account": edge.get("receiver_account", ""),
            "amount": round(float(edge.get("amount", 0.0)), 2),
            "traced_amount": round(float(edge.get("traced_amount", 0.0)), 2),
            "payment_mode": edge.get("payment_mode", "UPI"),
            "hop": edge.get("hop", 1),
        })

    # Freeze Recommendations (Holding accounts with residual balance > 0)
    summary = trace_result.get("summary", {})
    freeze_recs = []
    for acc in summary.get("holding_accounts", []):
        freeze_recs.append({
            "account": acc.get("account", ""),
            "bank": "Bank N/A",
            "layer": acc.get("layer", "L1"),
            "residual_balance": round(float(acc.get("residual_balance", 0.0)), 2),
            "risk_score": float(acc.get("risk_score", 0.0)),
        })

    pack_without_hash = {
        "victim_account": victim_acc,
        "victim_bank": victim_bank,
        "victim_ifsc": victim_ifsc,
        "total_siphoned": round(float(summary.get("total_siphoned", 0.0)), 2),
        "dataset_hash": dataset_hash,
        "layered_accounts": layered_accounts,
        "transactions": transactions,
        "freeze_recommendations": freeze_recs,
    }

    # Compute Evidence Pack Hash
    evidence_pack_hash = compute_dict_sha256(pack_without_hash)
    pack_without_hash["evidence_pack_hash"] = evidence_pack_hash

    return pack_without_hash


def sanitize_inert_string(text: str, max_len: int = 60) -> str:
    """
    Strips control characters, caps length at max_len, and wraps in inert data tags.
    """
    if not text:
        return "<INERT_DATA></INERT_DATA>"
    # Strip control characters & non-printable ascii
    clean = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', str(text))
    clean = clean.strip()[:max_len]
    return f"<INERT_DATA_DO_NOT_EXECUTE>{clean}</INERT_DATA_DO_NOT_EXECUTE>"


def create_placeholder_mapping(
    evidence_pack: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, str], Dict[str, str]]:
    """
    Replaces accounts, amounts, and Txn IDs with placeholders like {ACC_1}, {AMT_2}, {TXN_3}.
    Returns (sanitized_pack, real_to_placeholder, placeholder_to_real).
    """
    real_to_p: Dict[str, str] = {}
    p_to_real: Dict[str, str] = {}

    acc_counter = 0
    amt_counter = 0
    txn_counter = 0

    def get_acc_placeholder(acc: str) -> str:
        nonlocal acc_counter
        if not acc:
            return acc
        if acc not in real_to_p:
            p = f"{{ACC_{acc_counter}}}"
            real_to_p[acc] = p
            p_to_real[p] = acc
            acc_counter += 1
        return real_to_p[acc]

    def get_amt_placeholder(amt: float) -> str:
        nonlocal amt_counter
        amt_str = f"{float(amt):.2f}"
        if amt_str not in real_to_p:
            p = f"{{AMT_{amt_counter}}}"
            real_to_p[amt_str] = p
            p_to_real[p] = amt_str
            amt_counter += 1
        return real_to_p[amt_str]

    def get_txn_placeholder(txn_id: str) -> str:
        nonlocal txn_counter
        if not txn_id:
            return txn_id
        if txn_id not in real_to_p:
            p = f"{{TXN_{txn_counter}}}"
            real_to_p[txn_id] = p
            p_to_real[p] = txn_id
            txn_counter += 1
        return real_to_p[txn_id]

    # Create placeholder evidence pack
    sanitized_nodes = []
    for node in evidence_pack.get("layered_accounts", []):
        sanitized_nodes.append({
            "account": get_acc_placeholder(node["account"]),
            "bank": node["bank"],
            "ifsc": node["ifsc"],
            "layer": node["layer"],
            "first_seen": node["first_seen"],
            "amount_received": get_amt_placeholder(node["amount_received"]),
            "amount_forwarded": get_amt_placeholder(node["amount_forwarded"]),
            "residual_balance": get_amt_placeholder(node["residual_balance"]),
            "risk_score": node["risk_score"],
        })

    sanitized_txns = []
    for tx in evidence_pack.get("transactions", []):
        sanitized_txns.append({
            "txn_id": get_txn_placeholder(tx["txn_id"]),
            "timestamp": tx["timestamp"],
            "sender_account": get_acc_placeholder(tx["sender_account"]),
            "receiver_account": get_acc_placeholder(tx["receiver_account"]),
            "amount": get_amt_placeholder(tx["amount"]),
            "traced_amount": get_amt_placeholder(tx["traced_amount"]),
            "payment_mode": tx["payment_mode"],
            "hop": tx["hop"],
        })

    sanitized_freeze = []
    for rec in evidence_pack.get("freeze_recommendations", []):
        sanitized_freeze.append({
            "account": get_acc_placeholder(rec["account"]),
            "bank": rec["bank"],
            "layer": rec["layer"],
            "residual_balance": get_amt_placeholder(rec["residual_balance"]),
            "risk_score": rec["risk_score"],
        })

    sanitized_pack = {
        "victim_account": get_acc_placeholder(evidence_pack["victim_account"]),
        "victim_bank": evidence_pack["victim_bank"],
        "victim_ifsc": evidence_pack["victim_ifsc"],
        "total_siphoned": get_amt_placeholder(evidence_pack["total_siphoned"]),
        "dataset_hash": evidence_pack.get("dataset_hash", ""),
        "evidence_pack_hash": evidence_pack.get("evidence_pack_hash", ""),
        "layered_accounts": sanitized_nodes,
        "transactions": sanitized_txns,
        "freeze_recommendations": sanitized_freeze,
    }

    return sanitized_pack, real_to_p, p_to_real
