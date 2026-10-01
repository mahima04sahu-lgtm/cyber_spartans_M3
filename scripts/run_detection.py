"""
Abhedya-Chakra Detection Pipeline Runner.
Extracts per-account features, calculates Mule Risk Index (0-100), tags layers (L1/L2/L3),
persists results into `account_scores` table, and prints top 20 mule accounts.
"""

import argparse
import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import duckdb

from backend.core.features import compute_account_features
from backend.core.scoring import compute_mule_scores


def parse_args():
    parser = argparse.ArgumentParser(description="Run Abhedya-Chakra Mule Detection Engine")
    parser.add_argument("--db", type=str, default="data/db/abhedya.duckdb", help="DuckDB database file path")
    parser.add_argument("--config", type=str, default="configs/scoring.yaml", help="Scoring YAML config path")
    return parser.parse_args()


def run_detection_pipeline(db_path: str = "data/db/abhedya.duckdb", config_path: str = "configs/scoring.yaml", con: Optional[duckdb.DuckDBPyConnection] = None):
    start_time = time.time()
    
    close_at_end = False
    if con is None:
        if not os.path.exists(db_path):
            print(f"Error: Database file '{db_path}' not found. Run ingestion first.", file=sys.stderr)
            sys.exit(1)
        con = duckdb.connect(database=db_path)
        close_at_end = True

    print(f"=== Abhedya Mule Detection Engine starting ===")

    # Step 1: Feature Extraction
    t0 = time.time()
    feat_res = compute_account_features(con)
    feat_dur = time.time() - t0

    # Step 2: Mule Risk Scoring & Layering
    t0 = time.time()
    score_res = compute_mule_scores(con, config_path=config_path)
    score_dur = time.time() - t0

    total_duration = time.time() - start_time

    # Step 3: Fetch & Print Top 20 Highest Risk Mule Accounts
    top20 = con.execute("""
        SELECT 
            account_str,
            risk_score,
            layer,
            risk_band,
            top_reasons
        FROM account_scores
        ORDER BY risk_score DESC, in_count DESC
        LIMIT 20;
    """).fetchall()

    print("\n================ TOP 20 SUSPECTED MONEY MULE ACCOUNTS ================")
    print(f"{'Account':<14} | {'Score':<6} | {'Layer':<6} | {'Band':<8} | {'Top Reason Codes'}")
    print("-" * 80)
    for row in top20:
        acc, score, layer, band, reasons = row
        print(f"{acc:<14} | {score:6.1f} | {layer:<6} | {band:<8} | {reasons}")
    print("=====================================================================")

    print("\n================ MULE DETECTION BENCHMARK SUMMARY ================")
    print(f"  Total Accounts Analyzed  : {score_res['total_accounts']:,}")
    print(f"  Suspected Mule Accounts  : {score_res['mule_count']:,} (L1: {score_res['l1_count']}, L2: {score_res['l2_count']}, L3: {score_res['l3_count']})")
    print(f"  Feature Extraction Time  : {feat_dur:6.2f} seconds")
    print(f"  Mule Scoring Time        : {score_dur:6.2f} seconds")
    print(f"  TOTAL DETECTION RUNTIME  : {total_duration:6.2f} seconds")
    print("==================================================================\n")

    if close_at_end:
        con.close()
    return total_duration


def main():
    args = parse_args()
    run_detection_pipeline(args.db, args.config)


if __name__ == "__main__":
    main()
