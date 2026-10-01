"""
DuckDB Ingestion & Normalization Engine for Abhedya-Chakra.

Ingests 2,000,000+ CSV transactions in <= 60s, cleans invalid data, builds
normalized relational schemas, generates integer node mappings for CSR adjacency,
creates Parquet files, builds ART indexes, and logs benchmark timing.
"""

import argparse
import os
import sys
import time
from typing import Dict, Any, Tuple
import duckdb

from backend.core.config import (
    FOREIGN_IP_PREFIXES,
    HEADLESS_DEVICE_TYPES,
    NARRATION_CATEGORIES,
    BANK_IFSC_MAP,
    STRUCTURING_RANGES,
)


def get_duckdb_connection(db_path: str, memory_limit: str = "8GB") -> duckdb.DuckDBPyConnection:
    """Initialize persistent DuckDB connection with memory and thread limits."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    con = duckdb.connect(database=db_path)
    con.execute(f"SET memory_limit = '{memory_limit}';")
    con.execute(f"SET threads = {os.cpu_count() or 4};")
    return con


def build_bank_case_statement() -> Tuple[str, str]:
    """Build SQL CASE statement mapping IFSC prefix (first 4 chars) to Bank Name."""
    sender_cases = " ".join([f"WHEN substring(Sender_IFSC, 1, 4) = '{k}' THEN '{v.replace('\'', '\'\'')}'" for k, v in BANK_IFSC_MAP.items()])
    receiver_cases = " ".join([f"WHEN substring(Receiver_IFSC, 1, 4) = '{k}' THEN '{v.replace('\'', '\'\'')}'" for k, v in BANK_IFSC_MAP.items()])
    
    sender_sql = f"CASE {sender_cases} ELSE COALESCE(substring(Sender_IFSC, 1, 4), 'UNKNOWN') END"
    receiver_sql = f"CASE {receiver_cases} ELSE COALESCE(substring(Receiver_IFSC, 1, 4), 'UNKNOWN') END"
    
    return sender_sql, receiver_sql


def build_narration_case_statement() -> str:
    """Build SQL CASE statement for narration regex categorization."""
    cases = []
    for cat, pattern in NARRATION_CATEGORIES.items():
        # Escape pattern single quotes if any
        esc_pattern = pattern.replace("'", "''")
        cases.append(f"WHEN regexp_matches(Narration, '{esc_pattern}') THEN '{cat}'")
    return f"CASE {' '.join(cases)} ELSE 'other' END"


def build_structuring_sql() -> str:
    """Build SQL boolean expression for near-threshold structuring checks."""
    conditions = []
    for low, high in STRUCTURING_RANGES:
        conditions.append(f"(Amount >= {low} AND Amount <= {high})")
    return f"({' OR '.join(conditions)})"


def build_ip_foreign_sql() -> str:
    """Build SQL boolean expression for foreign IP detection."""
    conditions = [f"IP_Address LIKE '{prefix}%'" for prefix in FOREIGN_IP_PREFIXES]
    return f"({' OR '.join(conditions)})"


def build_device_headless_sql() -> str:
    """Build SQL boolean expression for headless device detection."""
    devices_str = ", ".join([f"'{d}'" for d in HEADLESS_DEVICE_TYPES])
    return f"(Device_Type IN ({devices_str}))"


from typing import Dict, Any, Tuple, Optional, Callable
import duckdb

# ... (rest of imports)

def run_ingestion_pipeline(
    csv_path: str,
    db_path: str = "data/db/abhedya.duckdb",
    parquet_path: str = "data/parquet/transactions.parquet",
    progress_callback: Optional[Callable[[str, int, str], None]] = None,
) -> Dict[str, Any]:
    """
    Executes end-to-end ingestion, cleaning, normalization, account mapping,
    Parquet export, and DuckDB ART indexing.
    """
    overall_start = time.time()
    benchmark_records = []
    
    print(f"=== Abhedya Ingestion Engine starting for CSV: {csv_path} ===")
    if progress_callback:
        progress_callback("1_csv_ingest", 15, "Stage 1: Ingesting raw CSV with explicit schema...")

    con = get_duckdb_connection(db_path)

    os.makedirs(os.path.dirname(os.path.abspath(parquet_path)), exist_ok=True)

    # -------------------------------------------------------------
    # Stage 1: Fast CSV Ingest to Staging Table
    # -------------------------------------------------------------
    t0 = time.time()
    print("Stage 1: Ingesting raw CSV with explicit schema...")
    
    con.execute("DROP TABLE IF EXISTS raw_txns;")
    con.execute(f"""
        CREATE TABLE raw_txns AS
        SELECT * FROM read_csv(
            '{csv_path}',
            header=True,
            parallel=True,
            types={{
                'Transaction_ID': 'VARCHAR',
                'Sender_Account': 'VARCHAR',
                'Receiver_Account': 'VARCHAR',
                'Sender_IFSC': 'VARCHAR',
                'Receiver_IFSC': 'VARCHAR',
                'Amount': 'DOUBLE',
                'Timestamp': 'VARCHAR',
                'Payment_Mode': 'VARCHAR',
                'Narration': 'VARCHAR',
                'IP_Address': 'VARCHAR',
                'Device_Type': 'VARCHAR'
            }}
        );
    """)
    
    raw_count = con.execute("SELECT count(*) FROM raw_txns").fetchone()[0]
    t1 = time.time()
    benchmark_records.append(("1_csv_ingest", t1 - t0))
    print(f"  Stage 1 complete: Loaded {raw_count:,} raw rows in {t1 - t0:.2f}s")

    # -------------------------------------------------------------
    # Stage 2: Clean-up & Ingest Reporting
    # -------------------------------------------------------------
    t0 = time.time()
    print("Stage 2: Cleaning & filtering invalid records...")
    if progress_callback:
        progress_callback("2_cleaning", 35, "Stage 2: Cleaning & filtering invalid records...")

    con.execute("""
        CREATE TABLE IF NOT EXISTS ingest_report (
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            category VARCHAR,
            dropped_count BIGINT,
            details VARCHAR
        );
    """)
    
    # Check dropped categories
    dup_count = con.execute("""
        SELECT count(*) - count(DISTINCT Transaction_ID) FROM raw_txns;
    """).fetchone()[0]
    
    invalid_acc_count = con.execute("""
        SELECT count(*) FROM raw_txns
        WHERE Sender_Account IS NULL OR Receiver_Account IS NULL
           OR NOT regexp_matches(Sender_Account, '^[A-Za-z0-9]{12}$')
           OR NOT regexp_matches(Receiver_Account, '^[A-Za-z0-9]{12}$');
    """).fetchone()[0]
    
    invalid_ts_count = con.execute("""
        SELECT count(*) FROM raw_txns
        WHERE Timestamp IS NULL OR TRY_CAST(Timestamp AS TIMESTAMP) IS NULL;
    """).fetchone()[0]
    
    invalid_amt_count = con.execute("""
        SELECT count(*) FROM raw_txns
        WHERE Amount IS NULL OR Amount <= 0;
    """).fetchone()[0]

    con.execute("DELETE FROM ingest_report;")
    con.execute(f"INSERT INTO ingest_report (category, dropped_count, details) VALUES ('duplicate_txn_id', {dup_count}, 'Exact duplicate Transaction_IDs');")
    con.execute(f"INSERT INTO ingest_report (category, dropped_count, details) VALUES ('invalid_account', {invalid_acc_count}, 'Non-12-character or NULL account numbers');")
    con.execute(f"INSERT INTO ingest_report (category, dropped_count, details) VALUES ('invalid_timestamp', {invalid_ts_count}, 'NULL or unparseable timestamps');")
    con.execute(f"INSERT INTO ingest_report (category, dropped_count, details) VALUES ('non_positive_amount', {invalid_amt_count}, 'Amount <= 0 or NULL');")

    # Create cleaned staging view/table
    con.execute("DROP TABLE IF EXISTS raw_txns_clean;")
    con.execute("""
        CREATE TABLE raw_txns_clean AS
        SELECT * FROM raw_txns
        WHERE Sender_Account IS NOT NULL AND Receiver_Account IS NOT NULL
          AND regexp_matches(Sender_Account, '^[A-Za-z0-9]{12}$')
          AND regexp_matches(Receiver_Account, '^[A-Za-z0-9]{12}$')
          AND Timestamp IS NOT NULL AND TRY_CAST(Timestamp AS TIMESTAMP) IS NOT NULL
          AND Amount IS NOT NULL AND Amount > 0
        QUALIFY ROW_NUMBER() OVER (PARTITION BY Transaction_ID ORDER BY Timestamp) = 1;
    """)
    
    clean_count = con.execute("SELECT count(*) FROM raw_txns_clean").fetchone()[0]
    t1 = time.time()
    benchmark_records.append(("2_cleaning", t1 - t0))
    print(f"  Stage 2 complete: Cleaned dataset contains {clean_count:,} valid rows (dropped {raw_count - clean_count:,} invalid/duplicates) in {t1 - t0:.2f}s")

    # -------------------------------------------------------------
    # Stage 3: Normalization & Feature Enrichment (`txn` table)
    # -------------------------------------------------------------
    t0 = time.time()
    print("Stage 3: Normalizing & enriching feature columns...")
    if progress_callback:
        progress_callback("3_normalization", 55, "Stage 3: Normalizing & enriching feature columns...")

    sender_bank_sql, receiver_bank_sql = build_bank_case_statement()
    narration_cat_sql = build_narration_case_statement()
    ip_foreign_sql = build_ip_foreign_sql()
    device_headless_sql = build_device_headless_sql()
    structuring_sql = build_structuring_sql()
    
    con.execute("DROP TABLE IF EXISTS txn;")
    con.execute(f"""
        CREATE TABLE txn AS
        SELECT 
            Transaction_ID AS txn_id,
            Sender_Account AS sender_acc,
            Receiver_Account AS receiver_acc,
            Sender_IFSC AS sender_ifsc,
            Receiver_IFSC AS receiver_ifsc,
            {sender_bank_sql} AS sender_bank,
            {receiver_bank_sql} AS receiver_bank,
            Amount AS amount,
            TRY_CAST(Timestamp AS TIMESTAMP) AS ts,
            epoch(TRY_CAST(Timestamp AS TIMESTAMP)) AS epoch_sec,
            Payment_Mode AS payment_mode,
            Narration AS narration,
            IP_Address AS ip_address,
            {ip_foreign_sql} AS ip_foreign,
            CASE WHEN ({ip_foreign_sql}) THEN 'foreign' ELSE 'domestic' END AS ip_class,
            Device_Type AS device_type,
            {device_headless_sql} AS device_headless,
            {narration_cat_sql} AS narration_category,
            CASE 
                WHEN Amount < 1000 THEN '<1k'
                WHEN Amount < 10000 THEN '1k-10k'
                WHEN Amount < 50000 THEN '10k-50k'
                WHEN Amount < 100000 THEN '50k-1L'
                ELSE '>1L'
            END AS amount_band,
            {structuring_sql} AS near_threshold
        FROM raw_txns_clean
        ORDER BY sender_acc, ts;
    """)
    
    t1 = time.time()
    benchmark_records.append(("3_normalization", t1 - t0))
    print(f"  Stage 3 complete: Normalized `txn` table populated in {t1 - t0:.2f}s")

    # -------------------------------------------------------------
    # Stage 4: Integer Node Mapping & `accounts` / `txn_int`
    # -------------------------------------------------------------
    t0 = time.time()
    print("Stage 4: Generating integer node IDs and `txn_int` CSR representation...")
    if progress_callback:
        progress_callback("4_integer_mapping", 75, "Stage 4: Generating integer node IDs & CSR representation...")

    con.execute("DROP TABLE IF EXISTS accounts;")
    con.execute("""
        CREATE TABLE accounts AS
        SELECT 
            account_str,
            (ROW_NUMBER() OVER (ORDER BY account_str) - 1)::INTEGER AS account_id
        FROM (
            SELECT sender_acc AS account_str FROM txn
            UNION
            SELECT receiver_acc AS account_str FROM txn
        );
    """)
    
    account_count = con.execute("SELECT count(*) FROM accounts").fetchone()[0]
    
    con.execute("DROP TABLE IF EXISTS txn_int;")
    con.execute("""
        CREATE TABLE txn_int AS
        SELECT 
            (ROW_NUMBER() OVER () - 1)::BIGINT AS txn_row_id,
            s.account_id AS sender_id,
            r.account_id AS receiver_id,
            t.ts,
            t.epoch_sec,
            t.amount,
            t.payment_mode,
            t.ip_foreign,
            t.device_headless,
            t.near_threshold
        FROM txn t
        JOIN accounts s ON t.sender_acc = s.account_str
        JOIN accounts r ON t.receiver_acc = r.account_str
        ORDER BY sender_id, epoch_sec;
    """)
    
    t1 = time.time()
    benchmark_records.append(("4_integer_mapping", t1 - t0))
    print(f"  Stage 4 complete: Mapped {account_count:,} unique accounts to int IDs in {t1 - t0:.2f}s")

    # -------------------------------------------------------------
    # Stage 5: Parquet Export & Indexing
    # -------------------------------------------------------------
    t0 = time.time()
    print(f"Stage 5: Exporting compressed Parquet ({parquet_path}) & creating DuckDB ART Indexes...")
    if progress_callback:
        progress_callback("5_parquet_and_indexes", 90, "Stage 5: Exporting compressed Parquet & creating ART indexes...")

    con.execute(f"""
        COPY (SELECT * FROM txn ORDER BY sender_acc, ts) 
        TO '{parquet_path}' (FORMAT PARQUET, COMPRESSION ZSTD);
    """)
    
    # Create ART Indexes for sub-second lookups
    con.execute("CREATE INDEX IF NOT EXISTS idx_txn_sender ON txn(sender_acc);")
    con.execute("CREATE INDEX IF NOT EXISTS idx_txn_receiver ON txn(receiver_acc);")
    con.execute("CREATE INDEX IF NOT EXISTS idx_accounts_str ON accounts(account_str);")
    con.execute("CREATE INDEX IF NOT EXISTS idx_accounts_id ON accounts(account_id);")
    con.execute("CREATE INDEX IF NOT EXISTS idx_txnint_sender ON txn_int(sender_id);")
    con.execute("CREATE INDEX IF NOT EXISTS idx_txnint_receiver ON txn_int(receiver_id);")
    
    t1 = time.time()
    benchmark_records.append(("5_parquet_and_indexes", t1 - t0))
    print(f"  Stage 5 complete: Exported Parquet & ART Indexes in {t1 - t0:.2f}s")

    # -------------------------------------------------------------
    # Stage 6: Persist Ingestion Benchmark
    # -------------------------------------------------------------
    total_duration = time.time() - overall_start
    benchmark_records.append(("total_pipeline", total_duration))
    
    con.execute("""
        CREATE TABLE IF NOT EXISTS ingest_benchmark (
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            stage_name VARCHAR,
            duration_seconds DOUBLE
        );
    """)
    
    for stage, dur in benchmark_records:
        con.execute(f"INSERT INTO ingest_benchmark (stage_name, duration_seconds) VALUES ('{stage}', {dur});")
        
    con.close()

    if progress_callback:
        progress_callback("complete", 100, f"Ingestion & Indexing Complete in {total_duration:.2f}s!")

    print("\n================ INGESTION BENCHMARK SUMMARY ================")
    for stage, dur in benchmark_records:
        print(f"  {stage:<25}: {dur:6.2f} seconds")
    print(f"  TOTAL INGESTION TIME     : {total_duration:6.2f} seconds")
    print("=============================================================\n")
    
    return {
        "raw_count": raw_count,
        "clean_count": clean_count,
        "account_count": account_count,
        "total_duration": total_duration,
        "benchmark_records": benchmark_records
    }


def main():
    parser = argparse.ArgumentParser(description="DuckDB Ingestion Engine for Abhedya-Chakra")
    parser.add_argument("--csv", type=str, default="data/raw/transactions.csv", help="Input CSV path")
    parser.add_argument("--db", type=str, default="data/db/abhedya.duckdb", help="Persistent DuckDB file path")
    parser.add_argument("--parquet", type=str, default="data/parquet/transactions.parquet", help="Output Parquet path")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"Error: Input CSV file '{args.csv}' not found. Please run generator first.", file=sys.stderr)
        sys.exit(1)

    run_ingestion_pipeline(args.csv, args.db, args.parquet)


if __name__ == "__main__":
    main()
