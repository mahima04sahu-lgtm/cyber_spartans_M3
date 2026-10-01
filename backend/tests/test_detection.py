"""
Unit tests for features.py and scoring.py money mule detection modules.
"""

import os
import duckdb
import pytest

from backend.core.ingest import run_ingestion_pipeline
from backend.core.features import compute_account_features
from backend.core.scoring import compute_mule_scores


@pytest.fixture
def temp_db(tmp_path):
    csv_file = tmp_path / "test_txns.csv"
    db_file = str(tmp_path / "test_abhedya.duckdb")
    parquet_file = str(tmp_path / "test_txns.parquet")

    # Generate sample test transactions
    with open(csv_file, "w", encoding="utf-8") as f:
        f.write("Transaction_ID,Sender_Account,Receiver_Account,Sender_IFSC,Receiver_IFSC,Amount,Timestamp,Payment_Mode,Narration,IP_Address,Device_Type\n")
        # Victim -> L1
        f.write("TXN001,910000000001,910000000002,SBIN0001234,HDFC0005678,100000.0,2026-09-01 10:00:00,UPI,Cyber Fraud,103.21.12.4,Android\n")
        # L1 -> L2 (rapid forwarding in 5 mins)
        f.write("TXN002,910000000002,910000000003,HDFC0005678,ICIC0009101,95000.0,2026-09-01 10:05:00,IMPS,Move Funds,117.55.20.1,Android\n")
        # L2 -> L3 (rapid forwarding in 5 mins, foreign IP, Web_Emulator)
        f.write("TXN003,910000000003,910000000004,ICIC0009101,UTIB0003344,92000.0,2026-09-01 10:10:00,NEFT,Crypto P2P USDT,185.220.101.5,Web_Emulator\n")
        # Normal transfer
        f.write("TXN004,910000000005,910000000006,SBIN0001234,HDFC0005678,500.0,2026-09-01 11:00:00,UPI,Salary,103.21.12.4,Android\n")

    run_ingestion_pipeline(str(csv_file), db_file, parquet_file)
    con = duckdb.connect(db_file)
    yield con
    con.close()


def test_compute_account_features(temp_db):
    res = compute_account_features(temp_db)
    assert res["account_count"] == 6

    df = temp_db.execute("SELECT * FROM account_features WHERE account_str = '910000000002'").fetchdf()
    assert len(df) == 1
    row = df.iloc[0]
    assert row["in_count"] == 1
    assert row["out_count"] == 1
    assert row["pass_through_ratio"] >= 0.90
    assert row["median_dwell_seconds"] == 300.0  # 5 mins


def test_compute_mule_scores(temp_db):
    compute_account_features(temp_db)
    score_res = compute_mule_scores(temp_db)

    assert score_res["total_accounts"] == 6

    # Verify L2/L3 classifications
    df_l3 = temp_db.execute("SELECT * FROM mule_risk WHERE account_str = '910000000004'").fetchdf()
    assert len(df_l3) == 1
    assert df_l3.iloc[0]["layer"] == "L3"
    assert df_l3.iloc[0]["risk_score"] >= 40.0
    assert "FOREIGN_IP" in df_l3.iloc[0]["reason_codes"] or "CRYPTO_WALLET" in df_l3.iloc[0]["reason_codes"]
