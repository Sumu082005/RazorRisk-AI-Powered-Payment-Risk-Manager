"""
Train Native Razorpay Transaction-Risk Model using IEEE-CIS Dataset.
Features mapped:
- TransactionAmt -> amount
- TransactionDT -> hour_of_day, day_of_week
- card4 -> card_network (visa, mastercard, discover, amex, other)
- card6 -> card_type (credit, debit, prepaid, other)
- P_emaildomain -> email_domain (top domains + other/missing)
- C1 -> attempts (velocity counter)
- card3 -> is_international (flag based on non-standard country code)

Evaluates on held-out stratified test set (20%) and saves pipeline to models/razorrisk_native_pipeline.joblib.
"""

import urllib.request
import io
import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    precision_recall_curve,
    auc,
    roc_auc_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix
)

sys.stdout.reconfigure(encoding='utf-8')

DATA_URL = "https://huggingface.co/datasets/aliceczr/ieee-fraud-detection/resolve/main/train_transaction.csv"
SAMPLE_SIZE = 75000  # High statistical power, fast training
TARGET_MODEL_PATH = "models/razorrisk_native_pipeline.joblib"

print(f"Streaming {SAMPLE_SIZE} records from IEEE-CIS dataset...")

cols_to_extract = [
    'isFraud', 'TransactionAmt', 'TransactionDT', 
    'card4', 'card6', 'P_emaildomain', 'C1', 'card3'
]

req = urllib.request.Request(DATA_URL, headers={'User-Agent': 'Mozilla/5.0'})
records = []

with urllib.request.urlopen(req, timeout=30) as r:
    header_line = r.readline().decode('utf-8').strip().split(',')
    idx_map = {col: header_line.index(col) for col in cols_to_extract if col in header_line}
    
    count = 0
    for line in r:
        try:
            parts = line.decode('utf-8', errors='ignore').strip().split(',')
            if len(parts) >= max(idx_map.values()) + 1:
                row = {col: parts[idx_map[col]] for col in cols_to_extract}
                records.append(row)
                count += 1
                if count >= SAMPLE_SIZE:
                    break
        except Exception:
            continue

print(f"Successfully streamed {len(records)} records.")
df = pd.DataFrame(records)

df['isFraud'] = pd.to_numeric(df['isFraud'], errors='coerce').fillna(0).astype(int)
df['amount'] = pd.to_numeric(df['TransactionAmt'], errors='coerce').fillna(0.0)

dt = pd.to_numeric(df['TransactionDT'], errors='coerce').fillna(0)
df['hour_of_day'] = ((dt // 3600) % 24).astype(float)
df['day_of_week'] = ((dt // (3600 * 24)) % 7).astype(float)

df['attempts'] = pd.to_numeric(df['C1'], errors='coerce').fillna(1.0)

card3_num = pd.to_numeric(df['card3'], errors='coerce').fillna(150)
df['is_international'] = (card3_num != 150).astype(int)

def clean_network(val):
    v = str(val).lower().strip()
    if 'visa' in v: return 'visa'
    if 'master' in v: return 'mastercard'
    if 'rupay' in v: return 'rupay'
    if 'discover' in v: return 'discover'
    if 'amex' in v or 'american' in v: return 'amex'
    return 'other'

def clean_type(val):
    v = str(val).lower().strip()
    if 'credit' in v: return 'credit'
    if 'debit' in v: return 'debit'
    if 'prepaid' in v: return 'prepaid'
    return 'other'

def clean_domain(val):
    v = str(val).lower().strip()
    if not v or v == 'nan': return 'missing'
    top = ['gmail.com', 'yahoo.com', 'hotmail.com', 'anonymous.com', 'outlook.com', 'aol.com', 'comcast.net']
    return v if v in top else 'other'

df['card_network'] = df['card4'].apply(clean_network)
df['card_type'] = df['card6'].apply(clean_type)
df['email_domain'] = df['P_emaildomain'].apply(clean_domain)

features_num = ['amount', 'hour_of_day', 'day_of_week', 'attempts', 'is_international']
features_cat = ['card_network', 'card_type', 'email_domain']
all_features = features_num + features_cat

X = df[all_features]
y = df['isFraud']

fraud_count = y.sum()
fraud_rate = fraud_count / len(y) * 100
print(f"Class distribution: Total={len(y)}, Fraud={fraud_count} ({fraud_rate:.2f}%)")

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, random_state=42, stratify=y
)

print(f"Training split: {len(X_train)} rows | Held-out test split: {len(X_test)} rows")

num_transformer = Pipeline([
    ('imputer', SimpleImputer(strategy='median')),
    ('scaler', StandardScaler())
])

cat_transformer = Pipeline([
    ('imputer', SimpleImputer(strategy='constant', fill_value='other')),
    ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
])

preprocessor = ColumnTransformer(
    transformers=[
        ('num', num_transformer, features_num),
        ('cat', cat_transformer, features_cat)
    ]
)

base_clf = HistGradientBoostingClassifier(
    max_iter=100,
    class_weight='balanced',
    random_state=42,
    learning_rate=0.08,
    min_samples_leaf=20
)

calibrated_clf = CalibratedClassifierCV(
    estimator=base_clf,
    method='isotonic',
    cv=3
)

native_pipeline = Pipeline([
    ('preprocessor', preprocessor),
    ('classifier', calibrated_clf)
])

print("Fitting calibrated native pipeline...")
native_pipeline.fit(X_train, y_train)

y_probs = native_pipeline.predict_proba(X_test)[:, 1]

precisions, recalls, thresholds = precision_recall_curve(y_test, y_probs)
pr_auc = auc(recalls, precisions)
roc_auc = roc_auc_score(y_test, y_probs)

f1_scores = 2 * (precisions * recalls) / np.maximum(precisions + recalls, 1e-8)
best_idx = np.argmax(f1_scores)
opt_threshold = float(thresholds[min(best_idx, len(thresholds)-1)]) if len(thresholds) > 0 else 0.35
operating_threshold = round(float(np.clip(opt_threshold, 0.20, 0.40)), 2)

y_pred = (y_probs >= operating_threshold).astype(int)

cm = confusion_matrix(y_test, y_pred)
tn, fp, fn, tp = cm.ravel()
prec = precision_score(y_test, y_pred, zero_division=0)
rec = recall_score(y_test, y_pred, zero_division=0)
f1 = f1_score(y_test, y_pred, zero_division=0)

eval_report = {
    "pr_auc": round(float(pr_auc), 4),
    "roc_auc": round(float(roc_auc), 4),
    "operating_threshold": operating_threshold,
    "precision": round(float(prec), 4),
    "recall": round(float(rec), 4),
    "f1": round(float(f1), 4),
    "test_size": len(y_test),
    "confusion_matrix": {
        "true_negatives": int(tn),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_positives": int(tp)
    },
    "feature_names": all_features,
    "model_type": "HistGradientBoosting (Isotonic Calibrated)",
    "training_records": len(X_train),
    "source_dataset": "IEEE-CIS Fraud Detection (Mapped Features)"
}

print("\n=== HELD-OUT TEST EVALUATION REPORT ===")
print(f"PR-AUC: {eval_report['pr_auc']}")
print(f"ROC-AUC: {eval_report['roc_auc']}")
print(f"Selected Threshold: {eval_report['operating_threshold']}")
print(f"Precision: {eval_report['precision'] * 100:.2f}%")
print(f"Recall: {eval_report['recall'] * 100:.2f}%")
print(f"F1 Score: {eval_report['f1']}")
print(f"Confusion Matrix: TP={tp}, FP={fp}, TN={tn}, FN={fn}")

os.makedirs("models", exist_ok=True)
joblib.dump(native_pipeline, TARGET_MODEL_PATH)
print(f"\nSaved native model to {TARGET_MODEL_PATH}")

with open("models/razorrisk_native_metrics.json", "w", encoding="utf-8") as f:
    json.dump(eval_report, f, indent=2)
print("Saved evaluation metadata to models/razorrisk_native_metrics.json")
