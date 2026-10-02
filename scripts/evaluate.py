"""
Evaluation Engine for Abhedya-Chakra Money Mule Detection.
Compares `account_scores` table against `data/raw/ground_truth.csv`.
Computes Precision, Recall, F1, per-layer accuracy, false positives/negatives breakdowns,
and exports reports to docs/eval_report.json and docs/eval_report.md.
"""

import argparse
import json
import os
import sys
import time
import duckdb
import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate Abhedya Mule Detection Performance")
    parser.add_argument("--db", type=str, default="data/db/abhedya.duckdb", help="DuckDB database path")
    parser.add_argument("--gt", type=str, default="data/raw/ground_truth.csv", help="Ground truth CSV path")
    parser.add_argument("--out-json", type=str, default="docs/eval_report.json", help="Output JSON report path")
    parser.add_argument("--out-md", type=str, default="docs/eval_report.md", help="Output Markdown report path")
    return parser.parse_args()


def run_evaluation(
    db_path: str = "data/db/abhedya.duckdb",
    gt_path: str = "data/raw/ground_truth.csv",
    out_json: str = "docs/eval_report.json",
    out_md: str = "docs/eval_report.md"
):
    start_time = time.time()
    
    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found.", file=sys.stderr)
        sys.exit(1)
        
    if not os.path.exists(gt_path):
        print(f"Error: Ground truth CSV '{gt_path}' not found.", file=sys.stderr)
        sys.exit(1)

    print(f"=== Abhedya Evaluation Engine starting ===")
    print(f"Database: {db_path} | Ground Truth: {gt_path}")

    # Load Ground Truth
    gt_df = pd.read_csv(gt_path)
    gt_df["account"] = gt_df["account"].astype(str)
    
    con = duckdb.connect(database=db_path, read_only=True)
    scores_df = con.execute("SELECT * FROM account_scores").fetchdf()
    con.close()
    
    scores_df["account_str"] = scores_df["account_str"].astype(str)

    # Merge Ground Truth with Predicted Scores
    merged = pd.merge(
        gt_df,
        scores_df,
        left_on="account",
        right_on="account_str",
        how="inner"
    )

    total_accounts = len(merged)
    actual_mules = merged[merged["is_mule"] == True]
    actual_normals = merged[merged["is_mule"] == False]
    num_actual_mules = len(actual_mules)
    num_actual_normals = len(actual_normals)

    print(f"Dataset Evaluation: {total_accounts:,} accounts ({num_actual_mules:,} mules, {num_actual_normals:,} normal)")

    # 1. Evaluate Metrics across Risk Thresholds (40, 50, 60, 70, 80)
    thresholds = [40, 50, 60, 70, 80]
    metrics_per_threshold = {}

    for thresh in thresholds:
        pred_positive = merged["risk_score"] >= thresh
        pred_negative = merged["risk_score"] < thresh
        actual_pos = merged["is_mule"] == True
        actual_neg = merged["is_mule"] == False

        tp = int((pred_positive & actual_pos).sum())
        fp = int((pred_positive & actual_neg).sum())
        tn = int((pred_negative & actual_neg).sum())
        fn = int((pred_negative & actual_pos).sum())

        precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
        recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
        f1 = round(2 * precision * recall / (precision + recall), 4) if (precision + recall) > 0 else 0.0
        fpr = round(fp / num_actual_normals, 4) if num_actual_normals > 0 else 0.0

        metrics_per_threshold[str(thresh)] = {
            "threshold": thresh,
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "false_positive_rate": fpr
        }

    # 2. Per-Layer Recall & Classification Accuracy (Default Threshold = 50)
    default_thresh_df = merged.copy()
    default_thresh_df["pred_mule"] = default_thresh_df["risk_score"] >= 50

    layer_metrics = {}
    for layer_name in ["L1", "L2", "L3"]:
        layer_actuals = default_thresh_df[default_thresh_df["layer_x"] == layer_name]
        total_layer_cnt = len(layer_actuals)
        recalled_cnt = int(layer_actuals["pred_mule"].sum())
        exact_layer_match_cnt = int((layer_actuals["layer_y"] == layer_name).sum())
        
        layer_recall = round(recalled_cnt / total_layer_cnt, 4) if total_layer_cnt > 0 else 0.0
        layer_acc = round(exact_layer_match_cnt / total_layer_cnt, 4) if total_layer_cnt > 0 else 0.0

        layer_metrics[layer_name] = {
            "total_count": total_layer_cnt,
            "recalled_count": recalled_cnt,
            "layer_recall": layer_recall,
            "exact_layer_match_count": exact_layer_match_cnt,
            "layer_accuracy": layer_acc
        }

    # 3. Top 30 False Positives (Legitimate accounts falsely flagged as mules)
    fps_df = default_thresh_df[default_thresh_df["pred_mule"] & ~default_thresh_df["is_mule"]].sort_values(
        by="risk_score", ascending=False
    ).head(30)

    top_30_fps = []
    for _, row in fps_df.iterrows():
        top_30_fps.append({
            "account": row["account"],
            "risk_score": float(row["risk_score"]),
            "predicted_layer": row["layer_y"],
            "top_reasons": row["top_reasons"],
            "pass_through_ratio": float(row["pass_through_ratio"]),
            "median_dwell_seconds": float(row["median_dwell_seconds"]),
            "foreign_ip_share": float(row["foreign_ip_share"]),
            "headless_device_share": float(row["headless_device_share"]),
            "burstiness": int(row["burstiness"]),
        })

    # 4. Top 30 False Negatives (Mule accounts missed)
    fns_df = default_thresh_df[~default_thresh_df["pred_mule"] & default_thresh_df["is_mule"]].sort_values(
        by="risk_score", ascending=True
    ).head(30)

    top_30_fns = []
    for _, row in fns_df.iterrows():
        top_30_fns.append({
            "account": row["account"],
            "actual_layer": row["layer_x"],
            "risk_score": float(row["risk_score"]),
            "top_reasons": row["top_reasons"],
            "pass_through_ratio": float(row["pass_through_ratio"]),
            "median_dwell_seconds": float(row["median_dwell_seconds"]),
            "foreign_ip_share": float(row["foreign_ip_share"]),
            "headless_device_share": float(row["headless_device_share"]),
            "burstiness": int(row["burstiness"]),
        })

    total_eval_time = round(time.time() - start_time, 2)

    # 5. Build Final JSON Report
    report_dict = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_accounts": total_accounts,
        "num_actual_mules": num_actual_mules,
        "num_actual_normals": num_actual_normals,
        "threshold_metrics": metrics_per_threshold,
        "layer_metrics": layer_metrics,
        "top_false_positives_count": len(top_30_fps),
        "top_false_negatives_count": len(top_30_fns),
        "top_30_false_positives": top_30_fps,
        "top_30_false_negatives": top_30_fns,
        "evaluation_duration_seconds": total_eval_time
    }

    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    os.makedirs(os.path.dirname(out_md), exist_ok=True)

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2)

    # 6. Build Markdown Report Table
    md_content = f"""# Abhedya-Chakra Money Mule Detection Evaluation Report

**Evaluation Timestamp**: {report_dict['timestamp']}  
**Dataset Overview**: {total_accounts:,} accounts ({num_actual_mules:,} ground truth mules, {num_actual_normals:,} normal accounts)

---

## 1. Performance Across Risk Score Thresholds

| Threshold | Precision | Recall | F1 Score | False Positives | False Positive Rate |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for t_key, m in metrics_per_threshold.items():
        md_content += f"| **{t_key}** | {m['precision']*100:.2f}% | {m['recall']*100:.2f}% | **{m['f1_score']*100:.2f}%** | {m['fp']:,} | {m['false_positive_rate']*100:.2f}% |\n"

    md_content += """
---

## 2. Per-Layer Detection Recall & Layer Accuracy (Threshold >= 50)

| Layer | Ground Truth Mules | Recalled Mules | Layer Recall | Exact Layer Match | Layer Accuracy |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for l_key, lm in layer_metrics.items():
        md_content += f"| **{l_key}** | {lm['total_count']:,} | {lm['recalled_count']:,} | **{lm['layer_recall']*100:.2f}%** | {lm['exact_layer_match_count']:,} | **{lm['layer_accuracy']*100:.2f}%** |\n"

    md_content += f"""
---

## 3. Sample Top False Positives Breakdown (Legitimate Accounts Falsely Flagged)

| Account | Risk Score | Predicted Layer | Pass Through % | Dwell (s) | Foreign IP % | Reason Codes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for fp in top_30_fps[:10]:
        md_content += f"| `{fp['account']}` | {fp['risk_score']:.1f} | {fp['predicted_layer']} | {fp['pass_through_ratio']*100:.0f}% | {fp['median_dwell_seconds']:.0f}s | {fp['foreign_ip_share']*100:.0f}% | {fp['top_reasons']} |\n"

    md_content += f"""
---

## 4. Sample Top False Negatives Breakdown (Missed Mule Accounts)

| Account | Actual Layer | Risk Score | Pass Through % | Dwell (s) | Foreign IP % | Reason Codes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for fn in top_30_fns[:10]:
        md_content += f"| `{fn['account']}` | {fn['actual_layer']} | {fn['risk_score']:.1f} | {fn['pass_through_ratio']*100:.0f}% | {fn['median_dwell_seconds']:.0f}s | {fn['foreign_ip_share']*100:.0f}% | {fn['top_reasons']} |\n"

    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"\n================ EVALUATION SUMMARY ================")
    m50 = metrics_per_threshold["50"]
    print(f"  Threshold >= 50: Precision = {m50['precision']*100:.2f}%, Recall = {m50['recall']*100:.2f}%, F1 = {m50['f1_score']*100:.2f}%")
    print(f"  False Positives Count: {m50['fp']:,} (FPR: {m50['false_positive_rate']*100:.2f}%)")
    print(f"  L1 Recall: {layer_metrics['L1']['layer_recall']*100:.1f}% | L2 Recall: {layer_metrics['L2']['layer_recall']*100:.1f}% | L3 Recall: {layer_metrics['L3']['layer_recall']*100:.1f}%")
    print(f"  JSON Report saved to: {out_json}")
    print(f"  Markdown Report saved to: {out_md}")
    print(f"====================================================\n")

    return report_dict


def main():
    args = parse_args()
    run_evaluation(args.db, args.gt, args.out_json, args.out_md)


if __name__ == "__main__":
    main()
