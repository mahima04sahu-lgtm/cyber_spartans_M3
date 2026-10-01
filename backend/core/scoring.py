"""
Mule Risk Index scoring engine for Abhedya-Chakra.
Computes 0-100 risk score, human-readable reason codes, legit hub whitelist discounting,
L1/L2/L3 money mule layer classification, and risk bands.
"""

import os
import time
from typing import Dict, Any, List, Tuple
import duckdb


DEFAULT_CONFIG = {
    "weights": {
        "pass_through": 25.0,
        "rapid_forward": 20.0,
        "foreign_ip": 15.0,
        "headless_device": 15.0,
        "crypto_wallet_narration": 10.0,
        "structuring": 10.0,
        "cycle_detected": 10.0,
        "high_burstiness": 5.0,
    },
    "thresholds": {
        "pass_through_min": 0.85,
        "dwell_time_max_seconds": 900,
        "fanout_min": 3,
        "fanout_max": 7,
        "burstiness_high": 8,
    },
    "whitelist_hubs": {
        "max_pass_through": 0.35,
        "min_dwell_seconds": 3600,
        "min_in_degree": 30,
        "discount_factor": 0.15,
    },
}


def load_scoring_config(config_path: str = "configs/scoring.yaml") -> Dict[str, Any]:
    """Load scoring configuration from YAML file or return defaults."""
    if os.path.exists(config_path):
        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Could not parse '{config_path}' ({e}), using default scoring parameters.")
    return DEFAULT_CONFIG


def compute_mule_scores(con: duckdb.DuckDBPyConnection, config_path: str = "configs/scoring.yaml") -> Dict[str, Any]:
    """
    Computes risk score (0-100), reason codes, layer tags (L1/L2/L3), and populates
    `mule_risk` and `account_scores` tables in DuckDB.
    """
    start_time = time.time()
    print("Executing Mule Risk Scoring Engine...")

    cfg = load_scoring_config(config_path)
    weights = cfg.get("weights", DEFAULT_CONFIG["weights"])
    thresholds = cfg.get("thresholds", DEFAULT_CONFIG["thresholds"])
    whitelist = cfg.get("whitelist_hubs", DEFAULT_CONFIG["whitelist_hubs"])

    # 1. Register python helper function for reason code generation if needed or compute via DuckDB SQL
    # Fetch all features from DuckDB
    df = con.execute("SELECT * FROM account_features;").fetchdf()

    scores = []
    layers = []
    risk_bands = []
    reason_codes_list = []
    top_3_reasons_list = []
    is_whitelisted_list = []

    for _, row in df.iterrows():
        acc = str(row["account_str"])
        in_cnt = int(row["in_count"])
        out_cnt = int(row["out_count"])
        total_in = float(row["total_in"])
        total_out = float(row["total_out"])
        distinct_s = int(row["distinct_senders"])
        distinct_r = int(row["distinct_receivers"])
        pass_through = float(row["pass_through_ratio"])
        median_dwell = float(row["median_dwell_seconds"])
        fanout = float(row["avg_fanout_slices"])
        foreign_ip_sh = float(row["foreign_ip_share"])
        headless_sh = float(row["headless_device_share"])
        crypto_sh = float(row["crypto_wallet_narration_share"])
        atm_sh = float(row["atm_share"])
        near_thresh_sh = float(row["near_threshold_share"])
        is_cycle = bool(row["is_cycle"])
        burstiness = int(row["burstiness"])

        # Calculate weighted score components
        raw_score = 0.0
        reasons = []

        # Feature 1: Pass Through Ratio >= 85%
        if pass_through >= thresholds.get("pass_through_min", 0.85):
            w = weights.get("pass_through", 25.0)
            raw_score += w
            reasons.append(f"PASS_THROUGH_{int(pass_through*100)}%")

        # Feature 2: Rapid Forwarding (Dwell time <= 15 mins = 900s)
        if pass_through >= 0.70 and median_dwell <= thresholds.get("dwell_time_max_seconds", 900):
            w = weights.get("rapid_forward", 20.0)
            raw_score += w
            dwell_mins = max(1, int(median_dwell / 60.0))
            reasons.append(f"RAPID_FORWARD_IN_{dwell_mins}MIN")

        # Feature 3: Foreign IP Share
        if foreign_ip_sh > 0.20:
            w = weights.get("foreign_ip", 15.0) * min(1.0, foreign_ip_sh * 1.5)
            raw_score += w
            reasons.append(f"FOREIGN_IP_{int(foreign_ip_sh*100)}%")

        # Feature 4: Headless Device Share (Web_Emulator / Linux_Script)
        if headless_sh > 0.20:
            w = weights.get("headless_device", 15.0) * min(1.0, headless_sh * 1.5)
            raw_score += w
            reasons.append(f"HEADLESS_DEVICE_{int(headless_sh*100)}%")

        # Feature 5: Crypto / Wallet / ATM Narration Share
        if crypto_sh > 0.20:
            w = weights.get("crypto_wallet_narration", 10.0) * min(1.0, crypto_sh * 1.5)
            raw_score += w
            reasons.append(f"CRYPTO_WALLET_NARRATION_{int(crypto_sh*100)}%")

        # Feature 6: Near-threshold structuring (Amounts just under ₹50k / ₹1L)
        if near_thresh_sh > 0.15:
            w = weights.get("structuring", 10.0)
            raw_score += w
            reasons.append(f"STRUCTURING_NEAR_THRESHOLD_{int(near_thresh_sh*100)}%")

        # Feature 7: Temporal Cycles (A->B->...->A within 72h)
        if is_cycle:
            w = weights.get("cycle_detected", 10.0)
            raw_score += w
            reasons.append("TEMPORAL_CYCLE_DETECTED")

        # Feature 8: High Burstiness (Max txns in 10-min window)
        if burstiness >= thresholds.get("burstiness_high", 8):
            w = weights.get("high_burstiness", 5.0)
            raw_score += w
            reasons.append(f"HIGH_BURSTINESS_{burstiness}_TXNS_10MIN")

        # Additional structural reason: Fan-in / Fan-out degree
        if distinct_s >= 10:
            reasons.append(f"FAN_IN_{distinct_s}_SENDERS")
        if fanout >= 2.5:
            reasons.append(f"FAN_OUT_{int(fanout)}_ACCOUNTS")

        # Whitelist Logic for Legitimate Hubs (Employers, Merchants, Utilities)
        # High degree, low pass-through (<= 0.35), long dwell time (>= 3600s)
        is_whitelisted = False
        if (distinct_s >= whitelist.get("min_in_degree", 30) or in_cnt >= 50) and pass_through <= whitelist.get("max_pass_through", 0.35) and median_dwell >= whitelist.get("min_dwell_seconds", 3600):
            is_whitelisted = True
            discount = whitelist.get("discount_factor", 0.15)
            raw_score *= discount
            reasons = ["WHITELISTED_LEGIT_HUB"] + reasons

        final_score = min(100.0, max(0.0, round(raw_score, 1)))

        # Layer Classification Engine (L1 Collector, L2 Distributor, L3 Terminal)
        layer = "none"
        if final_score >= 40.0:
            if foreign_ip_sh >= 0.30 or headless_sh >= 0.30 or atm_sh >= 0.20 or (total_in >= 10000 and pass_through < 0.20):
                layer = "L3"
            elif out_cnt >= 3 and fanout >= 2.0 and pass_through >= 0.65:
                layer = "L2"
            elif in_cnt >= 2 and pass_through >= 0.65 and median_dwell <= 1200:
                layer = "L1"

        # Risk Band
        if final_score >= 80.0:
            band = "Critical"
        elif final_score >= 60.0:
            band = "High"
        elif final_score >= 40.0:
            band = "Medium"
        else:
            band = "Low"

        top_3 = ", ".join(reasons[:3]) if reasons else "NORMAL_BEHAVIOR"
        all_reasons_str = ";".join(reasons) if reasons else "NORMAL_BEHAVIOR"

        scores.append(final_score)
        layers.append(layer)
        risk_bands.append(band)
        reason_codes_list.append(all_reasons_str)
        top_3_reasons_list.append(top_3)
        is_whitelisted_list.append(is_whitelisted)

    df["risk_score"] = scores
    df["layer"] = layers
    df["risk_band"] = risk_bands
    df["reason_codes"] = reason_codes_list
    df["top_reasons"] = top_3_reasons_list
    df["is_whitelisted"] = is_whitelisted_list

    # Persist in DuckDB `mule_risk` and `account_scores` tables
    con.execute("DROP TABLE IF EXISTS mule_risk;")
    con.execute("DROP TABLE IF EXISTS account_scores;")
    
    con.register("df_scored_view", df)
    
    con.execute("""
        CREATE TABLE mule_risk AS
        SELECT 
            account_str,
            risk_score,
            layer,
            risk_band,
            reason_codes,
            top_reasons,
            is_whitelisted
        FROM df_scored_view;
    """)

    con.execute("""
        CREATE TABLE account_scores AS
        SELECT * FROM df_scored_view;
    """)

    con.execute("CREATE INDEX IF NOT EXISTS idx_mule_risk_acc ON mule_risk(account_str);")
    con.execute("CREATE INDEX IF NOT EXISTS idx_acc_scores_acc ON account_scores(account_str);")

    duration = time.time() - start_time
    mule_count = len(df[df["risk_score"] >= 40.0])
    l1_cnt = len(df[df["layer"] == "L1"])
    l2_cnt = len(df[df["layer"] == "L2"])
    l3_cnt = len(df[df["layer"] == "L3"])

    print(f"Scoring Complete: Classified {mule_count:,} suspected mules (L1: {l1_cnt}, L2: {l2_cnt}, L3: {l3_cnt}) in {duration:.2f}s")

    return {
        "total_accounts": len(df),
        "mule_count": mule_count,
        "l1_count": l1_cnt,
        "l2_count": l2_cnt,
        "l3_count": l3_cnt,
        "duration_seconds": duration,
    }
