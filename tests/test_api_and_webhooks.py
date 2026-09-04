"""Comprehensive API, Webhook, Security, and Idempotency Test Suite for RazorRisk."""

import hmac
import hashlib
import json
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import get_settings
from app.storage.audit_store import AuditStore


@pytest.fixture
def client(tmp_path):
    """Test client with isolated temporary SQLite database."""
    test_db = str(tmp_path / "test_audit.db")
    settings = get_settings()
    settings.SQLITE_DB_PATH = test_db
    settings.RAZORPAY_KEY_ID = "rzp_test_mock_key_123"
    settings.RAZORPAY_KEY_SECRET = "mock_secret_abc_456"
    settings.RAZORPAY_WEBHOOK_SECRET = "mock_webhook_secret_789"
    
    with TestClient(app) as c:
        yield c


def generate_webhook_signature(body: bytes, secret: str) -> str:
    """Generate valid HMAC-SHA256 signature for test payloads."""
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()


def sample_risk_payload(fraud_tendency: bool = False) -> dict:
    """Generate sample structured transaction payload matching ULB benchmark schema."""
    # V14 and V17 are primary risk drivers
    v14_val = -18.0 if fraud_tendency else 0.05
    v17_val = -22.0 if fraud_tendency else -0.07
    v12_val = -15.0 if fraud_tendency else 0.14
    
    payload = {
        "transaction_id": f"tx_test_{uuid.uuid4().hex[:8]}",
        "Time": 45000.0,
        "Amount": 125.50 if not fraud_tendency else 950.00,
        "V1": -1.35, "V2": 0.45, "V3": 1.20, "V4": 0.85, "V5": -0.30,
        "V6": 0.20, "V7": 0.50, "V8": 0.10, "V9": -0.40, "V10": -0.20,
        "V11": 0.30, "V12": v12_val, "V13": 0.05, "V14": v14_val, "V15": -0.10,
        "V16": -0.25, "V17": v17_val, "V18": 0.10, "V19": -0.05, "V20": 0.08,
        "V21": -0.02, "V22": 0.15, "V23": -0.05, "V24": 0.40, "V25": -0.20,
        "V26": 0.10, "V27": 0.02, "V28": -0.01,
        "cost_profile": "BALANCED"
    }
    return payload


# =====================================================================
# 1. HEALTH CHECK TEST
# =====================================================================
def test_health_endpoint(client):
    """GET /health must return 200 OK and sanitized status payload."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "RazorRisk API"
    assert "environment" in data
    # Ensure no secrets leak
    assert "key" not in data
    assert "secret" not in data


# =====================================================================
# 2 & 3. RISK SCORING TESTS
# =====================================================================
def test_risk_scoring_success(client):
    """POST /api/v1/risk/score must score transaction and return structured decision."""
    payload = sample_risk_payload(fraud_tendency=False)
    response = client.post("/api/v1/risk/score", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["transaction_id"] == payload["transaction_id"]
    assert "decision_id" in data
    assert "risk_score" in data
    assert data["risk_tier"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert data["confidence_tier"] in ["HIGH_CONFIDENCE", "MEDIUM_CONFIDENCE", "LOW_CONFIDENCE"]
    assert data["recommended_action"] in ["APPROVE", "REVIEW", "BLOCK"]
    assert "estimated_expected_loss" in data
    assert isinstance(data["triggered_rules"], list)
    assert isinstance(data["explanation_factors"], list)


def test_risk_scoring_high_risk_detection(client):
    """POST /api/v1/risk/score must detect severe anomaly and recommend BLOCK or REVIEW."""
    payload = sample_risk_payload(fraud_tendency=True)
    response = client.post("/api/v1/risk/score", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["risk_score"] > 0.30
    assert data["recommended_action"] in ["BLOCK", "REVIEW"]


# =====================================================================
# 4. MALFORMED RISK INPUT VALIDATION
# =====================================================================
def test_risk_scoring_malformed_missing_feature(client):
    """Missing required feature must return 422 Unprocessable Entity."""
    payload = sample_risk_payload()
    del payload["V14"]  # Remove required feature
    response = client.post("/api/v1/risk/score", json=payload)
    assert response.status_code == 422


def test_risk_scoring_negative_amount(client):
    """Negative amount must fail Pydantic validation with 422."""
    payload = sample_risk_payload()
    payload["Amount"] = -50.0
    response = client.post("/api/v1/risk/score", json=payload)
    assert response.status_code == 422


# =====================================================================
# 5 & 6. RAZORPAY ORDERS ENDPOINT TESTS (MOCKED)
# =====================================================================
def test_create_order_success(client, monkeypatch):
    """POST /api/v1/razorpay/orders must create order without leaking secret."""
    mock_order_id = "order_mock_123456"
    
    def mock_create_order(self, amount, currency="INR", receipt=None, notes=None):
        return {
            "id": mock_order_id,
            "entity": "order",
            "amount": amount,
            "currency": currency,
            "receipt": receipt,
            "status": "created"
        }

    monkeypatch.setattr("app.services.razorpay_client.RazorpayClient.create_order", mock_create_order)
    
    payload = {
        "amount": 50000,
        "currency": "INR",
        "receipt": "rcpt_1001"
    }
    response = client.post("/api/v1/razorpay/orders", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["order_id"] == mock_order_id
    assert data["amount"] == 50000
    assert data["currency"] == "INR"
    assert data["key_id"] == "rzp_test_mock_key_123"
    # CRITICAL: Verify secret is not in response
    assert "mock_secret_abc_456" not in response.text
    assert "key_secret" not in data


def test_create_order_invalid_input(client):
    """Invalid amount (< 100 paise / ₹1, negative, or > 10,000,000 paise / ₹100,000) or unsupported currency must return 422."""
    # Zero amount
    resp1 = client.post("/api/v1/razorpay/orders", json={"amount": 0, "currency": "INR"})
    assert resp1.status_code == 422
    
    # Amount below minimum 100 paise (₹1)
    resp_sub_min = client.post("/api/v1/razorpay/orders", json={"amount": 50, "currency": "INR"})
    assert resp_sub_min.status_code == 422

    # Amount above maximum 10,000,000 paise (₹100,000)
    resp_over_max = client.post("/api/v1/razorpay/orders", json={"amount": 10000001, "currency": "INR"})
    assert resp_over_max.status_code == 422

    # Unsupported currency
    resp2 = client.post("/api/v1/razorpay/orders", json={"amount": 1000, "currency": "XYZ"})
    assert resp2.status_code == 422



# =====================================================================
# 7, 8, 9. RAZORPAY WEBHOOK SIGNATURE VERIFICATION TESTS
# =====================================================================
def test_webhook_valid_signature_payment_authorized(client):
    """POST /webhooks/razorpay with valid HMAC signature must succeed."""
    settings = get_settings()
    event_payload = {
        "entity": "event",
        "account_id": "acc_mock_123",
        "event": "payment.authorized",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_mock_auth_01",
                    "entity": "payment",
                    "amount": 25000,
                    "currency": "INR",
                    "status": "authorized",
                    "order_id": "order_mock_01"
                }
            }
        },
        "created_at": 1700000000
    }
    
    body = json.dumps(event_payload).encode("utf-8")
    sig = generate_webhook_signature(body, settings.RAZORPAY_WEBHOOK_SECRET)
    
    response = client.post(
        "/webhooks/razorpay",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "x-razorpay-event-id": "evt_test_auth_001"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["event_type"] == "payment.authorized"
    assert data["action_taken"] in ("APPROVE", "REVIEW", "BLOCK")
    assert data["processing_status"] in ("NATIVE_AI_SCORED", "MODEL_NOT_APPLICABLE")


def test_webhook_with_legitimate_benchmark_features_runs_ai_scoring(client):
    """
    When legitimate benchmark features are attached to payment notes,
    WebhookService must run the Reference Benchmark ML pipeline rather than falling back.
    """
    settings = get_settings()
    bench_payload = sample_risk_payload(fraud_tendency=False)
    
    # Attach legitimate benchmark PCA features into payment notes
    notes = {f"V{i}": bench_payload[f"V{i}"] for i in range(1, 29)}
    notes["Time"] = bench_payload["Time"]

    event_payload = {
        "entity": "event",
        "account_id": "acc_mock_001",
        "event": "payment.captured",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_with_benchmark_001",
                    "amount": 12550,
                    "currency": "INR",
                    "status": "captured",
                    "order_id": "order_mock_02",
                    "notes": notes
                }
            }
        },
        "created_at": 1700000000
    }
    
    body = json.dumps(event_payload).encode("utf-8")
    sig = generate_webhook_signature(body, settings.RAZORPAY_WEBHOOK_SECRET)
    
    response = client.post(
        "/webhooks/razorpay",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "x-razorpay-event-id": "evt_test_ai_001"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["processing_status"] in ("BENCHMARK_AI_SCORED", "AI_ANALYZED")
    assert data["action_taken"] in ("APPROVE", "REVIEW", "BLOCK")
    assert data["decision_id"] is not None


def test_webhook_raw_fields_runs_native_ai_scoring(client):
    """
    When raw Razorpay webhook arrives without benchmark PCA features,
    WebhookService extracts genuine fields and runs the Native ML model (NATIVE_AI_SCORED).
    """
    settings = get_settings()

    event_payload = {
        "entity": "event",
        "account_id": "acc_mock_001",
        "event": "payment.captured",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_native_test_001",
                    "amount": 5000,
                    "currency": "INR",
                    "status": "captured",
                    "order_id": "order_native_001",
                    "method": "card",
                    "international": False,
                    "email": "customer@gmail.com",
                    "contact": "+919876543210",
                    "card": {
                        "network": "Visa",
                        "type": "credit"
                    },
                    "created_at": 1700000000
                }
            },
            "order": {
                "entity": {
                    "id": "order_native_001",
                    "amount": 5000,
                    "attempts": 1
                }
            }
        },
        "created_at": 1700000000
    }

    body = json.dumps(event_payload).encode("utf-8")
    sig = generate_webhook_signature(body, settings.RAZORPAY_WEBHOOK_SECRET)

    response = client.post(
        "/webhooks/razorpay",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "x-razorpay-event-id": "evt_native_001"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["processing_status"] == "NATIVE_AI_SCORED"
    assert data["action_taken"] in ("APPROVE", "REVIEW", "BLOCK")
    assert data["decision_id"] is not None




def test_webhook_invalid_signature_rejected(client):
    """Invalid signature must be rejected with 400 Bad Request."""
    body = b'{"event": "payment.captured"}'
    response = client.post(
        "/webhooks/razorpay",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": "invalid_tampered_signature_hex"
        }
    )
    assert response.status_code == 400
    assert "Invalid or missing X-Razorpay-Signature" in response.json()["detail"]


def test_webhook_missing_signature_rejected(client):
    """Missing signature header must be rejected with 400 Bad Request."""
    body = b'{"event": "payment.captured"}'
    response = client.post(
        "/webhooks/razorpay",
        content=body,
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400


# =====================================================================
# 10. WEBHOOK IDEMPOTENCY TEST
# =====================================================================
def test_webhook_idempotent_duplicate_handling(client):
    """Submitting the exact same webhook event ID twice must return duplicate status without reprocessing."""
    settings = get_settings()
    event_id = f"evt_idempotent_{uuid.uuid4().hex[:8]}"
    event_payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_dup_01",
                    "amount": 10000,
                    "currency": "INR"
                }
            }
        }
    }
    
    body = json.dumps(event_payload).encode("utf-8")
    sig = generate_webhook_signature(body, settings.RAZORPAY_WEBHOOK_SECRET)
    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": sig,
        "x-razorpay-event-id": event_id
    }
    
    # 1. First submission -> processed
    resp1 = client.post("/webhooks/razorpay", content=body, headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "processed"
    
    # 2. Duplicate submission -> returns duplicate status safely (HTTP 200)
    resp2 = client.post("/webhooks/razorpay", content=body, headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "duplicate"
    assert data2["action_taken"] == "IDEMPOTENT_IGNORE"
    assert data2["processing_status"] == "DUPLICATE"


# =====================================================================
# 11 & 12. MALFORMED & UNSUPPORTED WEBHOOK TESTS
# =====================================================================
def test_webhook_malformed_json_payload(client):
    """Malformed non-JSON payload with valid signature must return 400."""
    settings = get_settings()
    malformed_body = b"NOT_VALID_JSON_BODY{{{"
    sig = generate_webhook_signature(malformed_body, settings.RAZORPAY_WEBHOOK_SECRET)
    
    response = client.post(
        "/webhooks/razorpay",
        content=malformed_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig
        }
    )
    assert response.status_code == 400
    assert "Malformed webhook JSON" in response.json()["detail"]


def test_webhook_unsupported_event_ignored(client):
    """Unsupported event types (e.g. subscription.charged) must return 200 ignored."""
    settings = get_settings()
    event_payload = {"event": "subscription.charged", "payload": {}}
    body = json.dumps(event_payload).encode("utf-8")
    sig = generate_webhook_signature(body, settings.RAZORPAY_WEBHOOK_SECRET)
    
    response = client.post(
        "/webhooks/razorpay",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "x-razorpay-event-id": "evt_unsub_01"
        }
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


# =====================================================================
# 13, 14, 15, 16. MODEL NOT APPLICABLE, AUDIT LOG & SECRET LEAK TESTS
# =====================================================================
def test_webhook_model_not_applicable_fallback_and_audit(client):
    """Razorpay webhook lacks V1-V28 -> falls back to MODEL_NOT_APPLICABLE and logs audit."""
    settings = get_settings()
    event_id = f"evt_audit_check_{uuid.uuid4().hex[:6]}"
    event_payload = {
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_failed_99",
                    "amount": 75000,
                    "currency": "INR",
                    "order_id": "order_fail_99"
                }
            }
        }
    }
    body = json.dumps(event_payload).encode("utf-8")
    sig = generate_webhook_signature(body, settings.RAZORPAY_WEBHOOK_SECRET)
    
    response = client.post(
        "/webhooks/razorpay",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "x-razorpay-event-id": event_id
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["processing_status"] == "MODEL_NOT_APPLICABLE"
    assert data["action_taken"] == "REVIEW"
    
    # Verify Audit Store contains record
    store = AuditStore(settings.SQLITE_DB_PATH)
    event_record = store.get_webhook_event(event_id)
    assert event_record is not None
    assert event_record["event_type"] == "payment.failed"
    assert event_record["processing_status"] == "MODEL_NOT_APPLICABLE"
    assert event_record["related_payment_id"] == "pay_failed_99"


def test_secrets_never_leaked_in_responses_or_errors(client):
    """Verify that neither KEY_SECRET nor WEBHOOK_SECRET are ever returned in HTTP bodies."""
    settings = get_settings()
    secret1 = settings.RAZORPAY_KEY_SECRET
    secret2 = settings.RAZORPAY_WEBHOOK_SECRET
    
    # Test health
    r1 = client.get("/health")
    assert secret1 not in r1.text and secret2 not in r1.text
    
    # Test 404
    r2 = client.get("/nonexistent_path")
    assert secret1 not in r2.text and secret2 not in r2.text
    
    # Test 422 error
    r3 = client.post("/api/v1/risk/score", json={"invalid": "data"})
    assert secret1 not in r3.text and secret2 not in r3.text
    
    # Test 400 error
    r4 = client.post("/webhooks/razorpay", content=b"{}", headers={"X-Razorpay-Signature": "wrong"})
    assert secret1 not in r4.text and secret2 not in r4.text
    
    # Test checkout page
    r5 = client.get("/test-checkout")
    assert secret1 not in r5.text and secret2 not in r5.text


def test_test_checkout_endpoint(client):
    """GET /test-checkout must return 200 OK and render HTML test page with Razorpay Checkout.js."""
    response = client.get("/test-checkout")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "checkout.razorpay.com/v1/checkout.js" in response.text
    assert "/api/v1/razorpay/orders" in response.text
    assert "Temporary Test Page" in response.text
    assert "amountInput" in response.text
    assert "Test Mode" in response.text


# =====================================================================
# 17. MULTI-EVENT WEBHOOK DELIVERY IDEMPOTENCY TEST
# =====================================================================
def test_webhook_multi_event_scoring_idempotency(client):
    """
    When Razorpay sends multiple webhook events for the SAME payment transaction
    (e.g., payment.authorized, order.paid, payment.captured), exactly ONE NATIVE_AI_SCORED
    audit event must be created in audit_logs, while all webhook deliveries are tracked in webhook_events.
    """
    settings = get_settings()
    payment_id = f"pay_test_multi_{uuid.uuid4().hex[:8]}"
    order_id = f"order_test_multi_{uuid.uuid4().hex[:8]}"
    
    events = [
        ("evt_auth_01", "payment.authorized"),
        ("evt_order_01", "order.paid"),
        ("evt_cap_01", "payment.captured")
    ]
    
    for event_id, event_type in events:
        event_payload = {
            "event": event_type,
            "payload": {
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "amount": 5000,
                        "currency": "INR",
                        "order_id": order_id,
                        "method": "card",
                        "card": {
                            "network": "Visa",
                            "type": "credit"
                        },
                        "email": "customer@gmail.com"
                    }
                },
                "order": {
                    "entity": {
                        "id": order_id,
                        "amount": 5000,
                        "currency": "INR",
                        "attempts": 1
                    }
                }
            }
        }
        body = json.dumps(event_payload).encode("utf-8")
        sig = generate_webhook_signature(body, settings.RAZORPAY_WEBHOOK_SECRET)
        
        response = client.post(
            "/webhooks/razorpay",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": sig,
                "x-razorpay-event-id": event_id
            }
        )
        assert response.status_code == 200
        assert response.json()["status"] == "processed"
        assert response.json()["processing_status"] == "NATIVE_AI_SCORED"

    # Verify audit store state
    store = AuditStore(settings.SQLITE_DB_PATH)
    
    # All 3 distinct webhook event IDs should be recorded in webhook_events
    for event_id, _ in events:
        wh_rec = store.get_webhook_event(event_id)
        assert wh_rec is not None
        assert wh_rec["related_payment_id"] == payment_id
        assert wh_rec["processing_status"] == "NATIVE_AI_SCORED"

    # Crucial assertion: Exactly ONE NATIVE_AI_SCORED event in audit_logs for this transaction
    audit_res = store.get_audit_logs(transaction_id=payment_id)
    scoring_logs = [item for item in audit_res["items"] if item["event_type"] == "NATIVE_AI_SCORED"]
    assert len(scoring_logs) == 1, f"Expected exactly 1 NATIVE_AI_SCORED event, found {len(scoring_logs)}"
    assert scoring_logs[0]["transaction_id"] == payment_id
    assert scoring_logs[0]["risk_score"] is not None


