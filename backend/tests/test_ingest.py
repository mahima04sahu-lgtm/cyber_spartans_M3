"""
Unit tests for DuckDB Ingestion Engine (backend/core/ingest.py).
"""

import os
import tempfile
import duckdb
import pandas as pd
import pytest

from backend.core.ingest import run_ingestion_pipeline, get_duckdb_connection


@pytest.fixture
def sample_csv(tmp_path):
    csv_file = tmp_path / "sample_transactions.csv"
    data = [
        {
            "Transaction_ID": "TXN0000000001",
            "Sender_Account": "910000000001",
            "Receiver_Account": "910000000002",
            "Sender_IFSC": "SBIN0001234",
            "Receiver_IFSC": "HDFC0005678",
            "Amount": 49500.0,
            "Timestamp": "2026-09-01 10:00:00",
            "Payment_Mode": "UPI",
            "Narration": "Crypto P2P USDT transfer",
            "IP_Address": "185.220.101.5",
            "Device_Type": "Web_Emulator",
        },
        {
            "Transaction_ID": "TXN0000000002",
            "Sender_Account": "910000000002",
            "Receiver_Account": "910000000003",
            "Sender_IFSC": "HDFC0005678",
            "Receiver_IFSC": "ICIC0009101",
            "Amount": 1500.0,
            "Timestamp": "2026-09-01 10:05:00",
            "Payment_Mode": "IMPS",
            "Narration": "Salary Credit",
            "IP_Address": "49.36.12.4",
            "Device_Type": "Android",
        },
        # Duplicate TXN ID (should be dropped)
        {
            "Transaction_ID": "TXN0000000001",
            "Sender_Account": "910000000001",
            "Receiver_Account": "910000000002",
            "Sender_IFSC": "SBIN0001234",
            "Receiver_IFSC": "HDFC0005678",
            "Amount": 49500.0,
            "Timestamp": "2026-09-01 10:00:00",
            "Payment_Mode": "UPI",
            "Narration": "Crypto P2P USDT transfer",
            "IP_Address": "185.220.101.5",
            "Device_Type": "Web_Emulator",
        },
        # Invalid account number (should be dropped)
        {
            "Transaction_ID": "TXN0000000003",
            "Sender_Account": "123", # short account
            "Receiver_Account": "910000000003",
            "Sender_IFSC": "SBIN0001234",
            "Receiver_IFSC": "ICIC0009101",
            "Amount": 500.0,
            "Timestamp": "2026-09-01 10:10:00",
            "Payment_Mode": "UPI",
            "Narration": "P2P",
            "IP_Address": "103.21.12.4",
            "Device_Type": "iOS",
        },
        # Non-positive amount (should be dropped)
        {
            "Transaction_ID": "TXN0000000004",
            "Sender_Account": "910000000001",
            "Receiver_Account": "910000000003",
            "Sender_IFSC": "SBIN0001234",
            "Receiver_IFSC": "ICIC0009101",
            "Amount": -10.0,
            "Timestamp": "2026-09-01 10:15:00",
            "Payment_Mode": "UPI",
            "Narration": "Test",
            "IP_Address": "103.21.12.4",
            "Device_Type": "Android",
        }
    ]
    df = pd.DataFrame(data)
    df.to_csv(csv_file, index=False)
    return str(csv_file)


def test_run_ingestion_pipeline(sample_csv, tmp_path):
    db_file = str(tmp_path / "test_abhedya.duckdb")
    parquet_file = str(tmp_path / "test_transactions.parquet")

    result = run_ingestion_pipeline(sample_csv, db_file, parquet_file)

    assert result["raw_count"] == 5
    assert result["clean_count"] == 2
    assert result["account_count"] == 3

    # Verify DuckDB table schema & contents
    con = duckdb.connect(db_file)
    
    # 1. Verify ingest_report
    report_df = con.execute("SELECT * FROM ingest_report").fetchdf()
    assert len(report_df) == 4
    
    # 2. Verify normalized txn table
    txn_df = con.execute("SELECT * FROM txn").fetchdf()
    assert len(txn_df) == 2
    
    t1 = txn_df[txn_df["txn_id"] == "TXN0000000001"].iloc[0]
    assert t1["sender_bank"] == "State Bank of India"
    assert t1["receiver_bank"] == "HDFC Bank"
    assert t1["ip_foreign"] == True
    assert t1["ip_class"] == "foreign"
    assert t1["device_headless"] == True
    assert t1["narration_category"] == "crypto_p2p"
    assert t1["near_threshold"] == True
    
    t2 = txn_df[txn_df["txn_id"] == "TXN0000000002"].iloc[0]
    assert t2["sender_bank"] == "HDFC Bank"
    assert t2["receiver_bank"] == "ICICI Bank"
    assert t2["ip_foreign"] == False
    assert t2["ip_class"] == "domestic"
    assert t2["device_headless"] == False
    assert t2["narration_category"] == "salary"
    assert t2["near_threshold"] == False

    # 3. Verify accounts table
    acc_df = con.execute("SELECT * FROM accounts").fetchdf()
    assert len(acc_df) == 3
    assert set(acc_df["account_str"]) == {"910000000001", "910000000002", "910000000003"}

    # 4. Verify txn_int table
    txn_int_df = con.execute("SELECT * FROM txn_int").fetchdf()
    assert len(txn_int_df) == 2
    
    # 5. Verify Parquet file created
    assert os.path.exists(parquet_file)
    
    con.close()
