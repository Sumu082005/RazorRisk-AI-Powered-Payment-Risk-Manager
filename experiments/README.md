# RazorRisk — ML Experimentation Artifacts & Benchmark Registry

**Project:** RazorRisk (Razorpay AI Buildathon 2026 — AI Risk Manager Track)  
**Role:** ML Experimentation Lead  
**Last Run:** August 26, 2026  
**Reproducibility Seed:** `42`

---

## Overview of Experiment Artifacts

This directory contains empirical benchmark data generated from evaluating baseline and advanced machine learning models on the ULB Credit Card Fraud Detection dataset (`creditcard.csv`).

| File | Description | Key Contents |
|------|-------------|--------------|
| [`model_comparison.csv`](file:///c:/Users/sumuk/OneDrive/Documents/Desktop/RazorRisk/experiments/model_comparison.csv) | Full evaluation of 9 baseline and advanced models on validation set | PR-AUC, ROC-AUC, Precision, Recall, F1, TP/FP/TN/FN, FPR, FNR, Rec@Prec80, Rec@Prec90, Prec@Rec80, Brier Score, Training Time |
| [`split_comparison.csv`](file:///c:/Users/sumuk/OneDrive/Documents/Desktop/RazorRisk/experiments/split_comparison.csv) | Empirical comparison of 4 data splitting strategies | Row counts, fraud counts, fraud %, duplicate overlap count, leakage status, defensibility analysis |
| [`results.csv`](file:///c:/Users/sumuk/OneDrive/Documents/Desktop/RazorRisk/experiments/results.csv) | Final held-out test evaluation on primary and secondary splits | Out-of-sample PR-AUC, ROC-AUC, Precision, Recall, F1 across operating thresholds |
| [`threshold_analysis.csv`](file:///c:/Users/sumuk/OneDrive/Documents/Desktop/RazorRisk/experiments/threshold_analysis.csv) | Fine-grained sweep across 99 candidate decision thresholds | Threshold (0.01–0.99), Precision, Recall, F1, F2, F0.5, TP, FP, TN, FN |
| [`cost_analysis.csv`](file:///c:/Users/sumuk/OneDrive/Documents/Desktop/RazorRisk/experiments/cost_analysis.csv) | Asymmetric financial loss optimization under 3 business scenarios | Optimal threshold, total expected cost, false negative fraud loss, false positive friction cost, captured fraud % |
| [`calibration_results.csv`](file:///c:/Users/sumuk/OneDrive/Documents/Desktop/RazorRisk/experiments/calibration_results.csv) | Probability calibration assessment | Uncalibrated, Platt Scaling (Sigmoid), Isotonic Regression with Brier Score, Log Loss, Expected Calibration Error (ECE) |
| [`feature_importances.csv`](file:///c:/Users/sumuk/OneDrive/Documents/Desktop/RazorRisk/experiments/feature_importances.csv) | Gini feature importance ranking of the best Random Forest model | All 30 numerical features ranked by relative importance |
| [`robustness_results.csv`](file:///c:/Users/sumuk/OneDrive/Documents/Desktop/RazorRisk/experiments/robustness_results.csv) | Stress testing and edge case validation results | Idempotency, extreme amounts, zero-amount authorizations, boundary cases, OOD perturbations |

---

## Reproduction Instructions

All experiments can be re-run with:
```bash
python scratch/run_experiments.py
```
Outputs are written deterministically using `random_state=42`.
