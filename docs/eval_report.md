# Abhedya-Chakra Money Mule Detection Evaluation Report

**Evaluation Timestamp**: 2026-10-01 21:58:35  
**Dataset Overview**: 25,000 accounts (1,500 ground truth mules, 23,500 normal accounts)

---

## 1. Performance Across Risk Score Thresholds

| Threshold | Precision | Recall | F1 Score | False Positives | False Positive Rate |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **40** | 17.35% | 65.20% | **27.41%** | 4,660 | 19.83% |
| **50** | 100.00% | 43.20% | **60.34%** | 0 | 0.00% |
| **60** | 100.00% | 38.13% | **55.21%** | 0 | 0.00% |
| **70** | 100.00% | 22.80% | **37.13%** | 0 | 0.00% |
| **80** | 100.00% | 6.13% | **11.55%** | 0 | 0.00% |

---

## 2. Per-Layer Detection Recall & Layer Accuracy (Threshold >= 50)

| Layer | Ground Truth Mules | Recalled Mules | Layer Recall | Exact Layer Match | Layer Accuracy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **L1** | 300 | 5 | **1.67%** | 0 | **0.00%** |
| **L2** | 600 | 588 | **98.00%** | 41 | **6.83%** |
| **L3** | 600 | 55 | **9.17%** | 269 | **44.83%** |

---

## 3. Sample Top False Positives Breakdown (Legitimate Accounts Falsely Flagged)

| Account | Risk Score | Predicted Layer | Pass Through % | Dwell (s) | Foreign IP % | Reason Codes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |

---

## 4. Sample Top False Negatives Breakdown (Missed Mule Accounts)

| Account | Actual Layer | Risk Score | Pass Through % | Dwell (s) | Foreign IP % | Reason Codes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `910000018227` | L3 | 5.3 | 19% | 999999s | 41% | WHITELISTED_LEGIT_HUB, FOREIGN_IP_40%, HEADLESS_DEVICE_40% |
| `910000001669` | L3 | 5.4 | 26% | 999999s | 41% | WHITELISTED_LEGIT_HUB, FOREIGN_IP_40%, HEADLESS_DEVICE_40% |
| `910000007582` | L3 | 5.6 | 33% | 999999s | 43% | WHITELISTED_LEGIT_HUB, FOREIGN_IP_42%, HEADLESS_DEVICE_42% |
| `910000009645` | L3 | 5.8 | 24% | 999999s | 45% | WHITELISTED_LEGIT_HUB, FOREIGN_IP_44%, HEADLESS_DEVICE_44% |
| `910000022528` | L3 | 6.7 | 12% | 999999s | 53% | WHITELISTED_LEGIT_HUB, FOREIGN_IP_52%, HEADLESS_DEVICE_52% |
| `910000021815` | L3 | 10.0 | 43% | 454s | 20% | TEMPORAL_CYCLE_DETECTED, FAN_IN_79_SENDERS |
| `910000000128` | L1 | 10.0 | 24% | 518s | 0% | TEMPORAL_CYCLE_DETECTED, FAN_IN_1895_SENDERS |
| `910000000076` | L2 | 15.0 | 10% | 444s | 5% | TEMPORAL_CYCLE_DETECTED, HIGH_BURSTINESS_15_TXNS_10MIN, FAN_IN_1892_SENDERS |
| `910000000053` | L3 | 15.0 | 4% | 512s | 5% | TEMPORAL_CYCLE_DETECTED, HIGH_BURSTINESS_8_TXNS_10MIN, FAN_IN_1900_SENDERS |
| `910000000200` | L3 | 15.0 | 5% | 488s | 6% | TEMPORAL_CYCLE_DETECTED, HIGH_BURSTINESS_11_TXNS_10MIN, FAN_IN_1898_SENDERS |
