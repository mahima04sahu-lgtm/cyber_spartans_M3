"""
Hyperparameter Tuning Script for Abhedya-Chakra.
Optimizes weights and thresholds in `configs/scoring.yaml` using vectorized NumPy
evaluations to maximize F1 score while constraining FPR <= 3%.
"""

import argparse
import copy
import os
import sys
import time
import duckdb
import numpy as np
import pandas as pd
import yaml

from backend.core.scoring import compute_mule_scores, load_scoring_config


def parse_args():
    parser = argparse.ArgumentParser(description="Tune Abhedya Mule Risk Engine Hyperparameters")
    parser.add_argument("--db", type=str, default="data/db/abhedya.duckdb", help="DuckDB database path")
    parser.add_argument("--gt", type=str, default="data/raw/ground_truth.csv", help="Ground truth CSV path")
    parser.add_argument("--config", type=str, default="configs/scoring.yaml", help="Scoring YAML config path to update")
    parser.add_argument("--max-fpr", type=float, default=0.03, help="Maximum allowed false positive rate (default 0.03 = 3%)")
    return parser.parse_args()


def run_tuning(
    db_path: str = "data/db/abhedya.duckdb",
    gt_path: str = "data/raw/ground_truth.csv",
    config_path: str = "configs/scoring.yaml",
    max_fpr: float = 0.03
):
    start_time = time.time()

    if not os.path.exists(db_path) or not os.path.exists(gt_path):
        print(f"Error: Database or Ground Truth file missing.", file=sys.stderr)
        sys.exit(1)

    print("=== Abhedya Hyperparameter Tuning Engine Starting ===")
    print(f"Max Allowed FPR Constraint: {max_fpr*100:.1f}%")

    gt_df = pd.read_csv(gt_path)
    gt_df["account"] = gt_df["account"].astype(str)
    
    con = duckdb.connect(database=db_path)
    features_df = con.execute("SELECT * FROM account_features;").fetchdf()
    features_df["account_str"] = features_df["account_str"].astype(str)

    merged = pd.merge(gt_df, features_df, left_on="account", right_on="account_str", how="inner")
    
    is_mule = merged["is_mule"].values
    actual_pos_mask = is_mule == True
    actual_neg_mask = is_mule == False
    num_normals = np.sum(actual_neg_mask)

    # Base config
    base_cfg = load_scoring_config(config_path)

    # Search space definition
    pass_through_weights = [15.0, 20.0, 25.0, 30.0]
    rapid_forward_weights = [15.0, 20.0, 25.0]
    foreign_ip_weights = [15.0, 20.0]
    headless_device_weights = [15.0, 20.0]
    pass_through_mins = [0.80, 0.85, 0.90]

    best_score = -1.0
    best_config = copy.deepcopy(base_cfg)
    best_metrics = {}

    trials = 0
    
    # Vectorized features
    pt_ratio = merged["pass_through_ratio"].values
    dwell_sec = merged["median_dwell_seconds"].values
    f_ip = merged["foreign_ip_share"].values
    h_dev = merged["headless_device_share"].values
    c_nar = merged["crypto_wallet_narration_share"].values
    near_th = merged["near_threshold_share"].values
    cycles = merged["is_cycle"].values.astype(bool)
    bursts = merged["burstiness"].values
    in_cnts = merged["in_count"].values
    dist_s = merged["distinct_senders"].values

    for w_pt in pass_through_weights:
        for w_rf in rapid_forward_weights:
            for w_fip in foreign_ip_weights:
                for w_dev in headless_device_weights:
                    for pt_min in pass_through_mins:
                        trials += 1
                        
                        # Vectorized score calculation
                        score = np.zeros(len(merged), dtype=np.float64)
                        score += np.where(pt_ratio >= pt_min, w_pt, 0.0)
                        score += np.where((pt_ratio >= 0.70) & (dwell_sec <= 900.0), w_rf, 0.0)
                        score += np.where(f_ip > 0.20, w_fip * np.minimum(1.0, f_ip * 1.5), 0.0)
                        score += np.where(h_dev > 0.20, w_dev * np.minimum(1.0, h_dev * 1.5), 0.0)
                        score += np.where(c_nar > 0.20, 10.0 * np.minimum(1.0, c_nar * 1.5), 0.0)
                        score += np.where(near_th > 0.15, 10.0, 0.0)
                        score += np.where(cycles, 10.0, 0.0)
                        score += np.where(bursts >= 8, 5.0, 0.0)

                        # Whitelist discounting
                        whitelisted = ((dist_s >= 30) | (in_cnts >= 50)) & (pt_ratio <= 0.35) & (dwell_sec >= 3600.0)
                        score[whitelisted] *= 0.15
                        
                        score = np.clip(score, 0.0, 100.0)

                        pred_pos_mask = score >= 50.0

                        tp = np.sum(pred_pos_mask & actual_pos_mask)
                        fp = np.sum(pred_pos_mask & actual_neg_mask)
                        fn = np.sum((~pred_pos_mask) & actual_pos_mask)

                        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
                        fpr = fp / num_normals if num_normals > 0 else 0.0

                        if fpr <= max_fpr and f1 > best_score:
                            best_score = f1
                            best_config = copy.deepcopy(base_cfg)
                            best_config["weights"]["pass_through"] = float(w_pt)
                            best_config["weights"]["rapid_forward"] = float(w_rf)
                            best_config["weights"]["foreign_ip"] = float(w_fip)
                            best_config["weights"]["headless_device"] = float(w_dev)
                            best_config["thresholds"]["pass_through_min"] = float(pt_min)
                            
                            best_metrics = {
                                "precision": round(precision, 4),
                                "recall": round(recall, 4),
                                "f1_score": round(f1, 4),
                                "fpr": round(fpr, 4),
                                "fp": int(fp),
                                "tp": int(tp)
                            }

    # Save best configuration back to config_path
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(best_config, f)

    # Re-run detection scoring with best configuration in DuckDB
    compute_mule_scores(con, config_path=config_path)
    con.close()

    duration = round(time.time() - start_time, 2)

    print("\n================ HYPERPARAMETER TUNING COMPLETED ================")
    print(f"  Evaluated {trials} combinations in {duration} seconds!")
    print(f"  Best F1 Score Achieved  : {best_metrics.get('f1_score', 0.0)*100:.2f}%")
    print(f"  Precision               : {best_metrics.get('precision', 0.0)*100:.2f}%")
    print(f"  Recall                  : {best_metrics.get('recall', 0.0)*100:.2f}%")
    print(f"  False Positive Rate     : {best_metrics.get('fpr', 0.0)*100:.2f}% ({best_metrics.get('fp', 0)} accounts)")
    print(f"  Optimal Config Saved To : {config_path}")
    print("-----------------------------------------------------------------")
    print("  WARNING ON OVERFITTING TO SYNTHETIC DATA:")
    print("  Thresholds and weights tuned above are constrained to maintain explainable,")
    print("  domain-grounded rules (e.g. 15-min dwell time, >= 85% pass-through, foreign IP shares)")
    print("  so that the model generalizes to real bank telemetry without memorization.")
    print("=================================================================\n")


def main():
    args = parse_args()
    run_tuning(args.db, args.gt, args.config, args.max_fpr)


if __name__ == "__main__":
    main()
