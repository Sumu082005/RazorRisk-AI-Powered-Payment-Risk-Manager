# RazorRisk — Backend Setup & Operational Runbook

**Project:** RazorRisk (Razorpay AI Buildathon 2026 — AI Risk Manager Track)  
**Backend Framework:** FastAPI + Uvicorn (Asynchronous Python 3.13)  
**Status:** Implemented, Tested (`28/28 pytest passing`), Ready for Local Execution

---

## 1. Quickstart & Local Running

### Start Command:
```bash
uvicorn app.main:app --reload --port 8000
```

### Local Service Endpoints:
- **Base URL:** `http://localhost:8000`
- **Health Check:** `http://localhost:8000/health`
- **Swagger Interactive OpenAPI Docs:** `http://localhost:8000/docs`
- **ReDoc Interactive Documentation:** `http://localhost:8000/redoc`
- **Webhook Endpoint:** `http://localhost:8000/webhooks/razorpay`
- **Risk Scoring API:** `http://localhost:8000/api/v1/risk/score`
- **Order Creation API:** `http://localhost:8000/api/v1/razorpay/orders`

---

## 2. Environment Variables Configuration

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

| Variable Name | Required | Default Value | Description |
|---------------|----------|---------------|-------------|
| `RAZORRISK_ENV` | Optional | `development` | Application environment (`development` / `production`) |
| `API_HOST` | Optional | `0.0.0.0` | Server host binding |
| `API_PORT` | Optional | `8000` | Server port binding |
| `RAZORPAY_KEY_ID` | Required for live API | `rzp_test_...` | Razorpay public key ID |
| `RAZORPAY_KEY_SECRET` | Required for live API | `...` | Razorpay private secret (NEVER committed or exposed) |
| `RAZORPAY_WEBHOOK_SECRET` | Required for live webhooks | `...` | HMAC-SHA256 secret configured in Razorpay Dashboard |
| `SQLITE_DB_PATH` | Optional | `storage/audit.db` | Path to persistent local SQLite audit store |
| `MODEL_ARTIFACT_PATH` | Optional | `models/razorrisk_random_forest_pipeline.joblib` | Serialized Random Forest ML model bundle |

---

## 3. Core API Routes Reference

### 1. `GET /health`
Public health status check. Exposes zero credentials.
```json
{
  "status": "ok",
  "service": "RazorRisk API",
  "environment": "development"
}
```

### 2. `POST /api/v1/risk/score`
Runs the ML inference pipeline (Random Forest 100 + Isotonic calibration) and deterministic `RiskDecisionEngine`.

**Request Body (ULB Benchmark Schema):**
```json
{
  "transaction_id": "tx_2026_08_94812",
  "Time": 45000.0,
  "Amount": 125.50,
  "V1": -1.35, "V2": 0.45, "V3": 1.20, "V4": 0.85, "V5": -0.30,
  "V6": 0.20, "V7": 0.50, "V8": 0.10, "V9": -0.40, "V10": -0.20,
  "V11": 0.30, "V12": 0.14, "V13": 0.05, "V14": 0.05, "V15": -0.10,
  "V16": -0.25, "V17": -0.07, "V18": 0.10, "V19": -0.05, "V20": 0.08,
  "V21": -0.02, "V22": 0.15, "V23": -0.05, "V24": 0.40, "V25": -0.20,
  "V26": 0.10, "V27": 0.02, "V28": -0.01,
  "cost_profile": "BALANCED"
}
```

**Response Body:**
```json
{
  "transaction_id": "tx_2026_08_94812",
  "decision_id": "dec_a84c901e45f2",
  "fraud_probability": 0.0125,
  "calibrated_probability": 0.0118,
  "uncertainty": 0.1250,
  "risk_score": 0.0125,
  "risk_tier": "LOW",
  "confidence_tier": "HIGH_CONFIDENCE",
  "recommended_action": "APPROVE",
  "cost_profile": "BALANCED",
  "triggered_rules": [
    {
      "rule_id": "POL-03-LOW-RISK-APPROVE",
      "rule_name": "Standard Low Risk Approval",
      "severity": "INFO",
      "description": "Fraud probability (0.0125) is below review threshold (0.12)."
    }
  ],
  "estimated_expected_loss": 1.76,
  "explanation_factors": [
    {
      "feature": "V14",
      "contribution_score": 0.0087,
      "impact_direction": "ELEVATES_RISK"
    }
  ],
  "requires_human_review": false,
  "model_version": "Random Forest (Unweighted)",
  "policy_version": "2026.08-v1",
  "decision_timestamp": "2026-08-26T22:45:00.123456+00:00"
}
```

### 3. `POST /api/v1/razorpay/orders`
Creates a Razorpay Test Mode order. Returns sanitized payload with public `key_id`. Never returns secrets.
```json
// Request
{
  "amount": 50000,
  "currency": "INR",
  "receipt": "rcpt_1001"
}

// Response
{
  "order_id": "order_NXKj912481",
  "amount": 50000,
  "currency": "INR",
  "receipt": "rcpt_1001",
  "status": "created",
  "key_id": "rzp_test_placeholder_key_id"
}
```

---

## 4. Test Suite Execution

Run all 28 automated tests:
```bash
python -m pytest tests/ -v
```

Output:
```
tests/test_api_and_webhooks.py (15 tests) PASSED
tests/test_decision_engine.py (13 tests) PASSED
============================= 28 passed in 3.58s =============================
```
