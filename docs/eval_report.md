# Abhedya-Chakra Money Mule Detection Evaluation Report

**Evaluation Timestamp**: 2026-10-02 05:32:41  
**Dataset Overview**: 0 accounts (0 ground truth mules, 0 normal accounts)

---

## 1. Performance Across Risk Score Thresholds

| Threshold | Precision | Recall | F1 Score | False Positives | False Positive Rate |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **40** | 0.00% | 0.00% | **0.00%** | 0 | 0.00% |
| **50** | 0.00% | 0.00% | **0.00%** | 0 | 0.00% |
| **60** | 0.00% | 0.00% | **0.00%** | 0 | 0.00% |
| **70** | 0.00% | 0.00% | **0.00%** | 0 | 0.00% |
| **80** | 0.00% | 0.00% | **0.00%** | 0 | 0.00% |

---

## 2. Per-Layer Detection Recall & Layer Accuracy (Threshold >= 50)

| Layer | Ground Truth Mules | Recalled Mules | Layer Recall | Exact Layer Match | Layer Accuracy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **L1** | 0 | 0 | **0.00%** | 0 | **0.00%** |
| **L2** | 0 | 0 | **0.00%** | 0 | **0.00%** |
| **L3** | 0 | 0 | **0.00%** | 0 | **0.00%** |

---

## 3. Sample Top False Positives Breakdown (Legitimate Accounts Falsely Flagged)

| Account | Risk Score | Predicted Layer | Pass Through % | Dwell (s) | Foreign IP % | Reason Codes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |

---

## 4. Sample Top False Negatives Breakdown (Missed Mule Accounts)

| Account | Actual Layer | Risk Score | Pass Through % | Dwell (s) | Foreign IP % | Reason Codes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
