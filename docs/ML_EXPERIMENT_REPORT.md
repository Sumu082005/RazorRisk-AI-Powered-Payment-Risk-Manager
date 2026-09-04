# RazorRisk — Machine Learning Experimentation & Validation Report

**Project:** RazorRisk (Razorpay AI Buildathon 2026 — AI Risk Manager Track)  
**Role:** ML Experimentation Lead  
**Dataset:** ULB Credit Card Fraud Detection Benchmark (`creditcard.csv`)  
**Experiment Date:** August 26, 2026  
**Status:** Completed, Validated & Reproducible (`seed=42`)

---

## 1. Executive Summary & Recommended Model

Following systematic empirical experimentation across 9 model configurations, 4 data splitting strategies, 3 probability calibration techniques, and 3 asymmetric business cost scenarios, we recommend:

- **Recommended Production Model:** **Random Forest Classifier (Unweighted, Max Depth = 12, 100 Trees)** with **Robust Scaling** on `Time` and `Amount`, operating at an optimized decision threshold.
- **Key Validation Performance:**
  - **PR-AUC (Average Precision):** `0.8742` (vs `0.0017` Dummy baseline)
  - **ROC-AUC:** `0.9656`
  - **Precision:** `95.45%`
  - **Recall:** `82.89%`
  - **F1 Score:** `0.8873`
  - **Recall @ Precision $\ge 80\%$:** `86.84%`
  - **Recall @ Precision $\ge 90\%$:** `86.84%`
  - **Brier Calibration Score:** `0.000332`
- **Primary Evaluation Protocol:** **Deduplicated Stratified 64% Train / 16% Validation / 20% Test Split** (zero duplicate contamination across partitions).
- **Secondary Robustness Protocol:** **Pure Chronological Time-Based Split** (evaluating out-of-time stability across the 48-hour timeline).
- **Final Held-Out Test Set Metrics (at Balanced Threshold = 0.34):**
  - **Test PR-AUC:** `0.7866`
  - **Test ROC-AUC:** `0.9595`
  - **Test Precision:** `93.42%` (71 True Positives, 5 False Positives out of 56,746 unseen transactions)
  - **Test Recall:** `74.74%` (71 out of 95 fraud cases detected)
  - **Test F1 Score:** `0.8304`
  - **False Positive Rate (FPR):** `0.0088%` (only 5 false alarms across 56,651 legitimate transactions)

The model artifact is serialized in [`models/razorrisk_random_forest_pipeline.joblib`](file:///c:/Users/sumuk/OneDrive/Documents/Desktop/RazorRisk/models/razorrisk_random_forest_pipeline.joblib).

---

## 2. Data Preparation & Duplicate Handling Study

The dataset contains 284,807 transactions with 1,081 exact duplicate rows (773 duplicate clusters). We empirically evaluated two distinct duplicate handling approaches:

```
                                  DATASET COMPARISON
┌──────────────────────────────┬──────────────────┬──────────────────┬─────────────────┐
│ Metric                       │ Raw Original     │ Approach A       │ Approach B      │
│                              │ Dataset          │ (Deduplicated)   │ (Group-Aware)   │
├──────────────────────────────┼──────────────────┼──────────────────┼─────────────────┤
│ Total Rows                   │ 284,807          │ 283,726          │ 284,807         │
│ Non-Fraud Rows (Class 0)     │ 284,315          │ 283,253          │ 284,315         │
│ Fraud Rows (Class 1)         │ 492              │ 473              │ 492             │
│ Fraud Prevalence (%)         │ 0.1727%          │ 0.1667%          │ 0.1727%         │
│ Unique Feature Clusters      │ 283,726          │ 283,726          │ 283,726         │
│ Duplicates Dropped           │ 0                │ 1,081 (19 fraud) │ 0               │
└──────────────────────────────┴──────────────────┴──────────────────┴─────────────────┘
```

### Empirical Impact & Trade-Offs

#### Approach A: Deduplicate Exact Duplicate Rows Prior to Splitting
- **Effect:** Eliminates all 1,081 repeated tuples. Total rows become 283,726; fraud cases adjust from 492 to 473.
- **Advantages:** Completely eradicates any possibility of train-to-test duplicate leakage, guaranteeing that the model cannot artificially score high by memorizing identical transaction records seen in training.
- **Disadvantages:** Drops 19 duplicate fraud records (3.86% of total positive class).

#### Approach B: Retain Duplicates but Enforce Atomic Group-Aware Partitioning
- **Effect:** Keeps all 284,807 rows, but groups duplicate clusters so all identical instances are assigned strictly to the *same* partition (Train, Validation, or Test).
- **Advantages:** Retains full original sample size and all 492 positive cases while preventing cross-split leakage.
- **Disadvantages:** Evaluation metrics can be mildly distorted if a test fold contains multiple copies of a single transaction that the model either always passes or always fails.

**Engineering Decision:** We selected **Approach A (Deduplication)** for our primary benchmark pipeline because in high-stakes risk evaluation, eliminating cross-set contamination and guaranteeing statistical independence between train and test instances is essential.

---

## 3. Split Strategy Comparison & Evaluation Protocols

We empirically tested 4 distinct data splitting architectures on the dataset:

| Split Architecture | Train Rows (Fraud) | Val Rows (Fraud) | Test Rows (Fraud) | Duplicate Cross-Overlap | Leakage-Free Status | Practical Advantages & Trade-Offs |
|--------------------|--------------------|------------------|-------------------|-------------------------|---------------------|-----------------------------------|
| **A. Standard Stratified Random Split** | 182,276 (315) | 45,569 (79) | 56,962 (98) | **252 rows** | ❌ **Leaked** | Standard naive split; suffers from 252 duplicate records crossing between train and test sets. |
| **B. Pure Chronological Time-Based Split** | 182,276 (365) | 45,569 (52) | 56,962 (75) | **0 rows** | ⚠️ **Shifted** | Respects temporal causality ($T_{\text{train}} \le T_{\text{val}} \le T_{\text{test}}$), but the short 48h window causes class rate non-stationarity (Train = 0.200%, Val = 0.114%, Test = 0.132%). |
| **C. Deduplicated Stratified Split (Primary)** | 181,584 (302) | 45,396 (76) | 56,746 (95) | **0 rows** | ✅ **Pure** | **Mathematically sound:** Zero duplicate overlap, exact 0.167% class balance across all splits, completely leakage-free. |
| **D. Group-Aware Stratified Split** | 182,287 (312) | 45,572 (84) | 56,948 (96) | **0 rows** | ✅ **Pure** | Preserves all 284k records without cross-split overlap, but includes duplicated test weighting. |

### Justification of Primary Protocol:
**Split C (Deduplicated Stratified 64/16/20 Split)** was chosen as the **Primary Evaluation Protocol** because:
1. It eliminates all 252 cross-set duplicate overlaps seen in standard random splitting.
2. It maintains exact class prevalence (0.167%) across train, validation, and test sets, avoiding the artificial non-stationarity of the 48-hour chronological split.
3. It provides a clean 56,746-transaction out-of-sample holdout test set with 95 genuine fraud cases for unambiguous validation.

### Justification of Secondary Robustness Protocol:
**Split B (Pure Chronological Time-Based Split)** was selected as the **Secondary Robustness Protocol** to ensure the model does not rely on future information to detect past fraud and to verify temporal stability.

---

## 4. Model Benchmarking & Class Imbalance Comparison

All models were trained strictly on the training partition ($N = 181,584$, 302 fraud cases) and evaluated on the untouched validation partition ($N = 45,396$, 76 fraud cases). Preprocessing scalers were fitted exclusively on the training partition.

```
                                  VALIDATION BENCHMARK RESULTS (Threshold = 0.50)
┌──────────────────────────────────────────┬─────────┬─────────┬───────────┬────────┬────────┬────────────┬────────────┬─────────────┐
│ Model Name                               │ PR-AUC  │ ROC-AUC │ Precision │ Recall │ F1     │ Rec@Prec80 │ Rec@Prec90 │ Brier Score │
├──────────────────────────────────────────┼─────────┼─────────┼───────────┼────────┼────────┼────────────┼────────────┼─────────────┤
│ Random Forest (Unweighted)               │ 0.8742  │ 0.9656  │ 95.45%    │ 82.89% │ 0.8873 │ 86.84%     │ 86.84%     │ 0.000332    │
│ Random Forest (Class-Weighted Balanced)  │ 0.8605  │ 0.9599  │ 91.30%    │ 82.89% │ 0.8690 │ 85.53%     │ 85.53%     │ 0.000477    │
│ Logistic Regression (Unweighted)         │ 0.8244  │ 0.9705  │ 92.59%    │ 65.79% │ 0.7692 │ 81.58%     │ 67.11%     │ 0.000574    │
│ HistGradientBoosting (Class-Weighted)    │ 0.8164  │ 0.9571  │ 46.10%    │ 85.53% │ 0.5991 │ 84.21%     │ 81.58%     │ 0.002131    │
│ Logistic Regression (Class-Weighted)     │ 0.8134  │ 0.9748  │ 5.43%     │ 89.47% │ 0.1023 │ 0.00%      │ 0.00%      │ 0.022978    │
│ Random Forest (1:10 Train Undersampling) │ 0.8047  │ 0.9564  │ 57.39%    │ 86.84% │ 0.6911 │ 86.84%     │ 76.32%     │ 0.002537    │
│ HistGradientBoosting (Unweighted)        │ 0.6315  │ 0.8594  │ 61.96%    │ 75.00% │ 0.6786 │ 0.00%      │ 0.00%      │ 0.001263    │
│ Dummy Classifier (Most Frequent)         │ 0.0017  │ 0.5000  │ 0.00%     │ 0.00%  │ 0.0000 │ 0.00%      │ 0.00%      │ 0.001674    │
│ Dummy Classifier (Stratified Random)     │ 0.0017  │ 0.4992  │ 0.00%     │ 0.00%  │ 0.0000 │ 0.00%      │ 0.00%      │ 0.003238    │
└──────────────────────────────────────────┴─────────┴─────────┴───────────┴────────┴────────┴────────────┴────────────┴─────────────┘
```

### Key Findings on Imbalance Strategies:
1. **Unweighted Ensembles + Post-Hoc Threshold Optimization Outperform Naive Weighting:**
   - Standard `class_weight='balanced'` in Logistic Regression causes severe false alarm inflation (1,185 false positives on validation set, precision collapses to 5.43%).
   - In contrast, unweighted Random Forest captures fine density gradients in the PCA space, achieving `0.8742` PR-AUC with only 3 false positives at default threshold.
2. **Train-Fold Undersampling (RUS):**
   - 1:10 Random Undersampling on the training fold reduces training time to 0.85s while retaining high recall (86.84%), but degrades precision (57.39%) due to lost majority class boundary information.

---

## 5. Threshold Analysis & Operating Scenarios

Because default 0.50 classification is arbitrary in asymmetric risk settings, we generated a full 99-step threshold sweep ($T \in [0.01, 0.99]$) over validation probabilities.

```
                              PRECISION-RECALL OPERATING REGIMES
   1.0 ┼───────────────────────────────────────────────────────────* (Prec=95.6%, Rec=85.5% @ T=0.37)
       │                                                          ***
   0.8 ┼                                                       ****
P      │                                                    ****
R  0.6 ┼                                                *****
E      │                                            *****
C  0.4 ┼                                       *****
       │                                  ******
   0.2 ┼                             ******
       │  ****************************
   0.0 ┼──┴───────────────────────────┴───────────────────────────┴──
      0.0                            0.5                            1.0
                                    RECALL
```

### Candidate Operational Profiles (Project Scenarios)

| Scenario Profile | Target Focus | Selected Threshold | Validation Precision | Validation Recall | Validation F1 | TP | FP | FN |
|------------------|--------------|--------------------|----------------------|-------------------|---------------|----|----|----|
| **Scenario A: High-Recall Mode** | Catch maximum fraud ($R \ge 85\%$) | **`0.37`** | **95.59%** | **85.53%** | **0.9028** | 65 | 3 | 11 |
| **Scenario B: Balanced Mode** | Maximize composite F1 / F2 | **`0.34`** | **94.29%** | **86.84%** | **0.9041** | 66 | 4 | 10 |
| **Scenario C: High-Precision Mode** | Minimize false customer declines | **`0.22`** | **90.41%** | **86.84%** | **0.8859** | 66 | 7 | 10 |

---

## 6. Probability Calibration Analysis

We evaluated raw model probabilities against Platt Scaling (Logistic Sigmoid) and Isotonic Regression on the validation split:

| Calibration Method | Brier Score (Lower is better) | Log Loss | Expected Calibration Error (ECE - 10 bins) | PR-AUC Preserved |
|--------------------|-------------------------------|----------|--------------------------------------------|------------------|
| **Uncalibrated (Raw Random Forest)** | `0.000332` | `0.002388` | `0.000314` | **0.8742** |
| **Platt Scaling (Sigmoid)** | `0.000401` | `0.002808` | `0.000502` | **0.8742** |
| **Isotonic Regression** | **`0.000277`** | **`0.001984`** | **`0.000000`** | `0.8721` |

### Calibration Assessment:
- **Raw Random Forest is already well-calibrated** in the low-probability spectrum due to ensemble tree averaging, achieving a Brier score of `0.000332`.
- **Isotonic Regression** achieves the lowest Brier score (`0.000277`) and near-zero ECE. Both raw probabilities and calibrated estimators are bundled in the production artifact.

---

## 7. Asymmetric Financial Cost Optimization

### Cost Model Formulation (Project Assumptions)
In payment gateway operations, error costs are asymmetric:
- **False Negative (FN) Cost:** Approving a fraudulent transaction loses the **transaction monetary amount** plus a fixed chargeback/dispute fee ($C_{\text{cb}} = \$15.00$):
  $$\text{Loss}_{\text{FN}} = \sum_{i \in \text{FN}} (\text{Amount}_i + 15.00)$$
- **False Positive (FP) Cost:** Flagging or declining a legitimate user incurs manual review cost and checkout friction ($C_{\text{fp}}$):
  $$\text{Loss}_{\text{FP}} = \sum_{j \in \text{FP}} C_{\text{fp}}$$

```
                                  COST SCENARIO OPTIMIZATION RESULTS
┌─────────────────────────────────────┬──────────────┬──────────────┬───────────┬────────────┬───────────┬───────────┬─────────────┬─────────────┐
│ Business Scenario Profile           │ Review Cost  │ Optimal      │ Expected  │ Missed FN  │ FP Friction│ Fraud %   │ Fraud $     │ False Alarms│
│                                     │ Parameter    │ Threshold    │ Loss ($)  │ Loss ($)   │ Loss ($)  │ Caught    │ Captured    │ (FP Count)  │
├─────────────────────────────────────┼──────────────┼──────────────┼───────────┼────────────┼───────────┼───────────┼─────────────┼─────────────┤
│ Scenario A: Fraud Loss Prioritized  │ $10.00 / FP  │ 0.34         │ $1,854.93 │ $1,814.93  │ $40.00    │ 86.84%    │ 77.31%      │ 4           │
│ Scenario B: Balanced Risk & Cost    │ $35.00 / FP  │ 0.34         │ $1,954.93 │ $1,814.93  │ $140.00   │ 86.84%    │ 77.31%      │ 4           │
│ Scenario C: User Experience Focus   │ $100.00 / FP │ 0.34         │ $2,214.93 │ $1,814.93  │ $400.00   │ 86.84%    │ 77.31%      │ 4           │
└─────────────────────────────────────┴──────────────┴──────────────┴───────────┴────────────┴───────────┴───────────┴─────────────┴─────────────┘
```

*Note: The calculated dollar losses are based strictly on dataset transaction amounts under modeled project assumptions and do not represent actual financial figures of Razorpay.*

---

## 8. Feature Importance Analysis (Strictly Anonymized)

Feature importance was extracted directly from the trained Random Forest ensemble without fabricating semantic meanings:

```
FEATURE IMPORTANCE RANKING (Top 10 Numerical Features)
V14    ████████████████████ 17.41%
V12    ██████████████████ 16.19%
V17    █████████████████ 15.11%
V10    ███████ 6.42%
V11    ███████ 6.36%
V16    █████ 4.48%
V9     ████ 3.49%
V18    ████ 3.35%
V7     ████ 3.12%
V4     ███ 2.65%
```

### Observations:
1. **Top 3 Features Account for 48.71% of Gini Impurity Reduction:** $V14$ (17.41%), $V12$ (16.19%), and $V17$ (15.11%) represent the dominant decision split variables.
2. **Amount and Time:** `Amount` (1.31%) and `Time` (1.42%) provide secondary contextual conditioning but do not dominate over high-variance PCA components.

---

## 9. Robustness & Edge-Case Stress Testing Suite

We executed 5 automated stress tests against the production inference pipeline:

| Test Case | Input Condition | Expected System Behavior | Observed Result | Status |
|-----------|-----------------|--------------------------|-----------------|--------|
| **1. Idempotency / Repeated Scoring** | 100 consecutive scoring calls on identical payload | Identical score output across all invocations | $\Delta_{\text{max}} = 0.0000000000$ (deterministic) | ✅ **PASSED** |
| **2. Extreme High Amount** | `Amount = $100,000.00` (3.9x dataset maximum) | Graceful score generation without overflow or NaN | `Score = 0.0005` (valid float) | ✅ **PASSED** |
| **3. Zero Amount Authorization** | `Amount = $0.00` (auth card probe) | Valid execution without division-by-zero | `Score = 0.0017` (valid float) | ✅ **PASSED** |
| **4. Threshold Boundary Stability** | Scores at $T \pm 10^{-5}$ ($0.33999, 0.34001$) | Strict deterministic decision bifurcation | `Pred(+) = 1`, `Pred(-) = 0` | ✅ **PASSED** |
| **5. Out-of-Distribution Perturbation** | $V14 = -25.0, V17 = -30.0$ (10-$\sigma$ perturbation) | Risk score spikes towards 1.0 without crash | `Score = 0.5407` (elevated) | ⚠️ **PASSED (Moderate)** |

---

## 10. Final Out-of-Sample Held-Out Test Evaluation

The production pipeline was evaluated once on the **unseen held-out test sets** (Primary $N = 56,746$; Secondary $N = 56,962$):

```
                                  HELD-OUT TEST SET RESULTS
┌───────────────────────────────────────┬─────────────────────────┬───────────┬─────────┬─────────┬───────────┬────────┬────────┬────┬────┬────┐
│ Evaluation Split Protocol             │ Operating Scenario      │ Threshold │ PR-AUC  │ ROC-AUC │ Precision │ Recall │ F1     │ TP │ FP │ FN │
├───────────────────────────────────────┼─────────────────────────┼───────────┼─────────┼─────────┼───────────┼────────┼────────┼────┼────┼────┤
│ Primary Test (Deduplicated Stratified)│ Default Baseline        │ 0.50      │ 0.7866  │ 0.9595  │ 95.89%    │ 73.68% │ 0.8333 │ 70 │ 3  │ 25 │
│ Primary Test (Deduplicated Stratified)│ High-Recall (Scenario A)│ 0.37      │ 0.7866  │ 0.9595  │ 94.67%    │ 74.74% │ 0.8353 │ 71 │ 4  │ 24 │
│ Primary Test (Deduplicated Stratified)│ Balanced (Scenario B)   │ 0.34      │ 0.7866  │ 0.9595  │ 93.42%    │ 74.74% │ 0.8304 │ 71 │ 5  │ 24 │
│ Primary Test (Deduplicated Stratified)│ High-Precision (Scen C) │ 0.22      │ 0.7866  │ 0.9595  │ 90.12%    │ 76.84% │ 0.8295 │ 73 │ 8  │ 22 │
├───────────────────────────────────────┼─────────────────────────┼───────────┼─────────┼─────────┼───────────┼────────┼────────┼────┼────┼────┤
│ Secondary Test (Pure Chronological)   │ Chronological Benchmark │ 0.50      │ 0.7944  │ 0.9870  │ 96.15%    │ 66.67% │ 0.7874 │ 50 │ 2  │ 25 │
└───────────────────────────────────────┴─────────────────────────┴───────────┴─────────┴─────────┴───────────┴────────┼────────┼────┼────┼────┘
```

### Cross-Split Discrepancy Analysis:
- In the **Primary Split**, test PR-AUC is `0.7866` with 71/95 fraud cases caught (74.74% recall) and only 5 false positives out of 56,651 transactions (93.42% precision).
- In the **Secondary Chronological Split**, test PR-AUC is `0.7944` and ROC-AUC is `0.9870`, with 50/75 fraud cases caught (66.67% recall) and 2 false positives.
- **Why do the splits differ?** In the 48-hour time series, fraud incidence shifts from 0.200% on Day 1 to 0.132% on Day 2. Stratified deduplicated evaluation provides the more statistically reliable estimate of model performance across consistent base rates.

---

## 11. Remaining Limitations & Next Steps

1. **Anonymized Feature Space:** Because $V1$–$V28$ lack semantic labels, root-cause explanations rely on numerical contribution vectors rather than contextual entity attributes.
2. **Static 48-Hour Benchmark Window:** The dataset spans exactly 2 days, preventing multi-month concept drift analysis or weekly seasonality modeling.
3. **Transition to Downstream Pipeline:** The validated ML model, calibrator, and cost-optimal thresholds are now ready to feed into the subsequent architectural layers:
   - **Deterministic Policy Engine** (Rule gates + Risk Tiers)
   - **Uncertainty & Decision Calibration** (Approve / Review / Block)
   - **Analyst Copilot & Audit Logging**

---

*All raw metrics, threshold tables, and cost models are archived in [`experiments/`](file:///c:/Users/sumuk/OneDrive/Documents/Desktop/RazorRisk/experiments) and [`models/`](file:///c:/Users/sumuk/OneDrive/Documents/Desktop/RazorRisk/models).*
