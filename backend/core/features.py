"""
Feature extraction engine for Abhedya-Chakra money mule detection.
Computes graph topological, temporal, behavioral, and structural features
for all accounts in DuckDB SQL and materializes into `account_features` table.
"""

import time
import duckdb
from typing import Dict, Any


def compute_account_features(con: duckdb.DuckDBPyConnection) -> Dict[str, Any]:
    """
    Computes per-account features in DuckDB SQL and populates `account_features` table.
    """
    start_time = time.time()
    print("Extracting per-account features in DuckDB SQL...")

    # 1. Base Volume, Amount, & Degree Features
    con.execute("DROP TABLE IF EXISTS account_base_stats;")
    con.execute("""
        CREATE TABLE account_base_stats AS
        WITH senders AS (
            SELECT 
                sender_acc AS account_str,
                COUNT(*) AS out_count,
                SUM(amount) AS total_out,
                COUNT(DISTINCT receiver_acc) AS distinct_receivers,
                MIN(ts) AS first_out,
                MAX(ts) AS last_out
            FROM txn
            GROUP BY sender_acc
        ),
        receivers AS (
            SELECT 
                receiver_acc AS account_str,
                COUNT(*) AS in_count,
                SUM(amount) AS total_in,
                COUNT(DISTINCT sender_acc) AS distinct_senders,
                MIN(ts) AS first_in,
                MAX(ts) AS last_in
            FROM txn
            GROUP BY receiver_acc
        )
        SELECT 
            a.account_str,
            COALESCE(r.in_count, 0) AS in_count,
            COALESCE(s.out_count, 0) AS out_count,
            COALESCE(r.total_in, 0.0) AS total_in,
            COALESCE(s.total_out, 0.0) AS total_out,
            COALESCE(r.distinct_senders, 0) AS distinct_senders,
            COALESCE(s.distinct_receivers, 0) AS distinct_receivers,
            LEAST(COALESCE(r.first_in, s.first_out), COALESCE(s.first_out, r.first_in)) AS first_seen,
            GREATEST(COALESCE(r.last_in, s.last_out), COALESCE(s.last_out, r.last_in)) AS last_seen
        FROM accounts a
        LEFT JOIN senders s ON a.account_str = s.account_str
        LEFT JOIN receivers r ON a.account_str = r.account_str;
    """)

    # 2. Behavioral Features (IP, Device, Narration, Structuring shares)
    con.execute("DROP TABLE IF EXISTS account_behavior_stats;")
    con.execute("""
        CREATE TABLE account_behavior_stats AS
        WITH combined AS (
            SELECT sender_acc AS account_str, ip_foreign, device_headless, narration_category, near_threshold FROM txn
            UNION ALL
            SELECT receiver_acc AS account_str, ip_foreign, device_headless, narration_category, near_threshold FROM txn
        )
        SELECT 
            account_str,
            AVG(ip_foreign::INT) AS foreign_ip_share,
            AVG(device_headless::INT) AS headless_device_share,
            AVG(CASE WHEN narration_category IN ('crypto_p2p', 'wallet', 'atm_cash') THEN 1.0 ELSE 0.0 END) AS crypto_wallet_narration_share,
            AVG(CASE WHEN narration_category = 'atm_cash' THEN 1.0 ELSE 0.0 END) AS atm_share,
            AVG(near_threshold::INT) AS near_threshold_share
        FROM combined
        GROUP BY account_str;
    """)

    # 3. Burstiness (Max transactions in any 10-minute window)
    con.execute("DROP TABLE IF EXISTS account_burstiness;")
    con.execute("""
        CREATE TABLE account_burstiness AS
        WITH combined_txns AS (
            SELECT sender_acc AS account_str, epoch_sec FROM txn
            UNION ALL
            SELECT receiver_acc AS account_str, epoch_sec FROM txn
        ),
        window_counts AS (
            SELECT 
                account_str,
                COUNT(*) OVER (
                    PARTITION BY account_str 
                    ORDER BY epoch_sec 
                    RANGE BETWEEN 0 PRECEDING AND 600 FOLLOWING
                ) AS window_cnt
            FROM combined_txns
        )
        SELECT account_str, MAX(window_cnt) AS burstiness
        FROM window_counts
        GROUP BY account_str;
    """)

    # 4. Rapid Pass-Through & Dwell Time (Inflow -> Outflow in 3 to 15 mins)
    con.execute("DROP TABLE IF EXISTS account_dwell_stats;")
    con.execute("""
        CREATE TABLE account_dwell_stats AS
        WITH in_out_pairs AS (
            SELECT 
                t_in.receiver_acc AS account_str,
                epoch(t_out.ts) - epoch(t_in.ts) AS dwell_sec,
                t_out.receiver_acc AS downstream_acc
            FROM txn t_in
            JOIN txn t_out ON t_in.receiver_acc = t_out.sender_acc
            WHERE t_out.ts >= t_in.ts 
              AND t_out.ts <= t_in.ts + INTERVAL '15 MINUTE'
        ),
        fanout_per_inflow AS (
            SELECT 
                t_in.receiver_acc AS account_str,
                t_in.txn_id AS in_txn_id,
                COUNT(DISTINCT t_out.receiver_acc) AS fanout_cnt
            FROM txn t_in
            JOIN txn t_out ON t_in.receiver_acc = t_out.sender_acc
            WHERE t_out.ts >= t_in.ts 
              AND t_out.ts <= t_in.ts + INTERVAL '15 MINUTE'
            GROUP BY t_in.receiver_acc, t_in.txn_id
        )
        SELECT 
            p.account_str,
            COALESCE(MEDIAN(p.dwell_sec), 999999.0) AS median_dwell_seconds,
            COUNT(*) AS rapid_forward_count,
            COALESCE(AVG(f.fanout_cnt), 0.0) AS avg_fanout_slices
        FROM in_out_pairs p
        LEFT JOIN fanout_per_inflow f ON p.account_str = f.account_str
        GROUP BY p.account_str;
    """)

    # 5. Temporal Cycles (2-hop, 3-hop, 4-hop cycles within 72h)
    con.execute("DROP TABLE IF EXISTS account_cycles;")
    con.execute("""
        CREATE TABLE account_cycles AS
        WITH cycles_2hop AS (
            SELECT DISTINCT t1.sender_acc AS account_str
            FROM txn t1
            JOIN txn t2 ON t1.receiver_acc = t2.sender_acc AND t1.sender_acc = t2.receiver_acc
            WHERE t2.ts > t1.ts AND t2.ts <= t1.ts + INTERVAL '72 HOUR'
        ),
        cycles_3hop AS (
            SELECT DISTINCT t1.sender_acc AS account_str
            FROM txn t1
            JOIN txn t2 ON t1.receiver_acc = t2.sender_acc
            JOIN txn t3 ON t2.receiver_acc = t3.sender_acc AND t3.receiver_acc = t1.sender_acc
            WHERE t2.ts > t1.ts AND t3.ts > t2.ts AND t3.ts <= t1.ts + INTERVAL '72 HOUR'
        )
        SELECT account_str, TRUE AS is_cycle FROM cycles_2hop
        UNION
        SELECT account_str, TRUE AS is_cycle FROM cycles_3hop;
    """)

    # 6. Materialize Master `account_features` Table
    con.execute("DROP TABLE IF EXISTS account_features;")
    con.execute("""
        CREATE TABLE account_features AS
        SELECT 
            b.account_str,
            b.in_count,
            b.out_count,
            b.total_in,
            b.total_out,
            b.distinct_senders,
            b.distinct_receivers,
            CASE 
                WHEN b.total_in > 0 THEN LEAST(1.0, b.total_out / b.total_in) 
                ELSE 0.0 
            END AS pass_through_ratio,
            COALESCE(d.median_dwell_seconds, 999999.0) AS median_dwell_seconds,
            COALESCE(d.avg_fanout_slices, 0.0) AS avg_fanout_slices,
            COALESCE(bh.foreign_ip_share, 0.0) AS foreign_ip_share,
            COALESCE(bh.headless_device_share, 0.0) AS headless_device_share,
            COALESCE(bh.crypto_wallet_narration_share, 0.0) AS crypto_wallet_narration_share,
            COALESCE(bh.atm_share, 0.0) AS atm_share,
            COALESCE(bh.near_threshold_share, 0.0) AS near_threshold_share,
            COALESCE(c.is_cycle, FALSE) AS is_cycle,
            COALESCE(br.burstiness, 0) AS burstiness,
            COALESCE(epoch(b.last_seen) - epoch(b.first_seen), 0) / 3600.0 AS account_age_hours,
            CASE 
                WHEN (b.in_count + b.out_count) >= 10 AND (epoch(b.last_seen) - epoch(b.first_seen)) < 86400 THEN TRUE 
                ELSE FALSE 
            END AS sudden_activity_flag
        FROM account_base_stats b
        LEFT JOIN account_behavior_stats bh ON b.account_str = bh.account_str
        LEFT JOIN account_burstiness br ON b.account_str = br.account_str
        LEFT JOIN account_dwell_stats d ON b.account_str = d.account_str
        LEFT JOIN account_cycles c ON b.account_str = c.account_str;
    """)

    # Build index on account_features
    con.execute("CREATE INDEX IF NOT EXISTS idx_features_acc ON account_features(account_str);")

    duration = time.time() - start_time
    total_accs = con.execute("SELECT COUNT(*) FROM account_features;").fetchone()[0]
    print(f"Features extracted for {total_accs:,} accounts in {duration:.2f}s")
    
    return {
        "account_count": total_accs,
        "duration_seconds": duration
    }
