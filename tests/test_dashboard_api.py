"""Comprehensive test suite for Dashboard, Analytics, Review Queue, and System APIs."""

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
    test_db = str(tmp_path / "test_dashboard_audit.db")
    settings = get_settings()
    settings.SQLITE_DB_PATH = test_db
    settings.RAZORPAY_KEY_ID = "rzp_test_mock_key_123"
    settings.RAZORPAY_KEY_SECRET = "mock_secret_abc_456"
    settings.RAZORPAY_WEBHOOK_SECRET = "mock_webhook_secret_789"
    
    with TestClient(app) as c:
        yield c


def sample_benchmark_payload(fraud_tendency: bool = False, transaction_id: str = None) -> dict:
    """Generate valid ULB benchmark transaction payload."""
    v14_val = -18.0 if fraud_tendency else 0.05
    v17_val = -22.0 if fraud_tendency else -0.07
    v12_val = -15.0 if fraud_tendency else 0.14
    
    return {
        "transaction_id": transaction_id or f"tx_bench_{uuid.uuid4().hex[:8]}",
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


# =====================================================================
# 1. ANALYTICS / OVERVIEW TESTS
# =====================================================================
def test_analytics_overview_empty_db(client):
    """Empty database must return zeroed aggregates without error."""
    response = client.get("/api/v1/analytics/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["transactions_monitored"] == 0
    assert data["approved"] == 0
    assert data["review"] == 0
    assert data["blocked"] == 0
    assert data["total_amount"] == 0.0
    assert data["approval_rate_pct"] == 0.0
    assert data["decision_distribution"] == {"APPROVE": 0, "REVIEW": 0, "BLOCK": 0}


def test_analytics_overview_with_real_transactions(client):
    """Aggregates must accurately reflect stored transactions across all actions and tiers."""
    settings = get_settings()
    store = AuditStore(settings.SQLITE_DB_PATH)

    store.record_audit_log(
        audit_id="audit_agg_1",
        transaction_id="tx_agg_app",
        event_type="INTERNAL_RISK_SCORE",
        action="APPROVE",
        cost_profile="BALANCED",
        decision_id="dec_agg_1",
        risk_score=0.02,
        risk_tier="LOW",
        confidence_tier="HIGH_CONFIDENCE",
        expected_loss=5.0,
        details={"amount": 120.0, "currency": "INR"}
    )
    store.record_audit_log(
        audit_id="audit_agg_2",
        transaction_id="tx_agg_rev",
        event_type="RAZORPAY_WEBHOOK_PAYMENT_AUTHORIZED",
        action="REVIEW",
        cost_profile="BALANCED",
        decision_id="dec_agg_2",
        risk_score=0.45,
        risk_tier="MEDIUM",
        confidence_tier="LOW_CONFIDENCE",
        expected_loss=300.0,
        details={"amount": 300.0, "currency": "INR"}
    )
    store.record_audit_log(
        audit_id="audit_agg_3",
        transaction_id="tx_agg_blk",
        event_type="INTERNAL_RISK_SCORE",
        action="BLOCK",
        cost_profile="BALANCED",
        decision_id="dec_agg_3",
        risk_score=0.88,
        risk_tier="HIGH",
        confidence_tier="HIGH_CONFIDENCE",
        expected_loss=500.0,
        details={"amount": 500.0, "currency": "INR"}
    )

    response = client.get("/api/v1/analytics/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["transactions_monitored"] == 3
    assert data["approved"] == 1
    assert data["review"] == 1
    assert data["blocked"] == 1
    assert data["decision_distribution"]["APPROVE"] == 1
    assert data["decision_distribution"]["REVIEW"] == 1
    assert data["decision_distribution"]["BLOCK"] == 1
    assert data["total_amount"] == 920.0
    assert data["approval_rate_pct"] == 33.33
    assert data["ai_analyzed_count"] == 3
    assert data["model_not_applicable_count"] == 0
    assert data["ai_applicability_rate_pct"] == 100.0



# =====================================================================
# 2. TRANSACTIONS API TESTS
# =====================================================================
def test_transactions_list_empty_db(client):
    """Empty DB returns total=0 and empty items list."""
    response = client.get("/api/v1/transactions")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_transactions_list_pagination_and_filtering(client):
    """Transactions list supports limit, offset, and action filtering."""
    settings = get_settings()
    store = AuditStore(settings.SQLITE_DB_PATH)

    store.record_audit_log(
        audit_id="audit_t1",
        transaction_id="tx_approved_1",
        event_type="INTERNAL_RISK_SCORE",
        action="APPROVE",
        cost_profile="BALANCED",
        decision_id="dec_t1",
        expected_loss=10.0,
        details={"amount": 100.0, "currency": "INR"}
    )
    store.record_audit_log(
        audit_id="audit_t2",
        transaction_id="tx_blocked_1",
        event_type="INTERNAL_RISK_SCORE",
        action="BLOCK",
        cost_profile="BALANCED",
        decision_id="dec_t2",
        expected_loss=500.0,
        details={"amount": 500.0, "currency": "INR"}
    )
    store.record_audit_log(
        audit_id="audit_t3",
        transaction_id="tx_approved_2",
        event_type="INTERNAL_RISK_SCORE",
        action="APPROVE",
        cost_profile="BALANCED",
        decision_id="dec_t3",
        expected_loss=25.0,
        details={"amount": 250.0, "currency": "INR"}
    )

    # Total check
    r_all = client.get("/api/v1/transactions")
    assert r_all.status_code == 200
    assert r_all.json()["total"] == 3

    # Pagination: limit=2
    r_page = client.get("/api/v1/transactions?limit=2&offset=0")
    assert len(r_page.json()["items"]) == 2

    # Filter: status=BLOCK
    r_block = client.get("/api/v1/transactions?status=BLOCK")
    assert r_block.json()["total"] == 1
    assert r_block.json()["items"][0]["action"] == "BLOCK"
    assert r_block.json()["items"][0]["transaction_id"] == "tx_blocked_1"

    # Search filter
    r_search = client.get("/api/v1/transactions?search=tx_approved_1")
    assert r_search.json()["total"] == 1
    assert r_search.json()["items"][0]["transaction_id"] == "tx_approved_1"



def test_transaction_detail_success(client):
    """Transaction detail returns full audit details, rules, and history."""
    txn_id = "tx_detail_test_001"
    payload = sample_benchmark_payload(fraud_tendency=False, transaction_id=txn_id)
    score_res = client.post("/api/v1/risk/score", json=payload)
    assert score_res.status_code == 200

    detail_res = client.get(f"/api/v1/transactions/{txn_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["transaction_id"] == txn_id
    assert detail["action"] == "APPROVE"
    assert detail["risk_score"] is not None
    assert isinstance(detail["triggered_rules"], list)
    assert len(detail["history"]) >= 1


def test_transaction_detail_not_found(client):
    """Nonexistent transaction ID returns 404."""
    response = client.get("/api/v1/transactions/nonexistent_tx_999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# =====================================================================
# 3. REVIEW QUEUE & MANUAL ACTION TESTS
# =====================================================================
def test_review_queue_empty_db(client):
    """Empty DB returns total=0 for review queue."""
    response = client.get("/api/v1/review/queue")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_review_queue_filters_only_review_items(client):
    """Only transactions whose current state is REVIEW must appear in the queue."""
    settings = get_settings()
    store = AuditStore(settings.SQLITE_DB_PATH)

    # Directly insert records with different actions into audit store
    store.record_audit_log(
        audit_id="audit_rev_1",
        transaction_id="tx_rev_01",
        event_type="RAZORPAY_WEBHOOK_PAYMENT_AUTHORIZED",
        action="REVIEW",
        cost_profile="BALANCED",
        decision_id="dec_rev_01",
        expected_loss=500.0,
        details={"amount": 500.0, "currency": "INR"}
    )
    store.record_audit_log(
        audit_id="audit_app_1",
        transaction_id="tx_app_01",
        event_type="INTERNAL_RISK_SCORE",
        action="APPROVE",
        cost_profile="BALANCED",
        decision_id="dec_app_01",
        expected_loss=10.0,
        details={"amount": 100.0, "currency": "INR"}
    )

    r_queue = client.get("/api/v1/review/queue")
    assert r_queue.status_code == 200
    data = r_queue.json()
    assert data["total"] == 1
    assert data["items"][0]["transaction_id"] == "tx_rev_01"
    assert data["items"][0]["action"] == "REVIEW"


def test_manual_review_action_execution_and_preservation(client):
    """
    Submitting manual review action:
    - Changes transaction state
    - Preserves original automated decision in history
    - Records action source and timestamp
    - Removes transaction from review queue
    """
    settings = get_settings()
    store = AuditStore(settings.SQLITE_DB_PATH)

    txn_id = "tx_manual_review_test"
    store.record_audit_log(
        audit_id="audit_orig_01",
        transaction_id=txn_id,
        event_type="RAZORPAY_WEBHOOK_PAYMENT_AUTHORIZED",
        action="REVIEW",
        cost_profile="BALANCED",
        decision_id="dec_auto_01",
        expected_loss=750.0,
        details={"amount": 750.0, "currency": "INR"}
    )

    # 1. Verify in queue
    q1 = client.get("/api/v1/review/queue")
    assert q1.json()["total"] == 1

    # 2. Execute manual review: APPROVE
    action_res = client.post(
        f"/api/v1/review/{txn_id}/action",
        json={
            "action": "APPROVE",
            "notes": "Verified KYC documents and user phone verification.",
            "reason": "KYC_VERIFIED"
        }
    )
    assert action_res.status_code == 200
    action_data = action_res.json()
    assert action_data["success"] is True
    assert action_data["previous_action"] == "REVIEW"
    assert action_data["new_action"] == "APPROVE"
    assert action_data["transaction_id"] == txn_id

    # 3. Verify removed from review queue
    q2 = client.get("/api/v1/review/queue")
    assert q2.json()["total"] == 0

    # 4. Verify transaction detail contains full history without destroying original decision
    detail_res = client.get(f"/api/v1/transactions/{txn_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["action"] == "APPROVE"  # Current state
    assert len(detail["history"]) == 2

    # Original decision preserved
    orig_history = [h for h in detail["history"] if h["action"] == "REVIEW"][0]
    assert orig_history["event_type"] == "RAZORPAY_WEBHOOK_PAYMENT_AUTHORIZED"

    # Manual action recorded with source and notes
    manual_history = [h for h in detail["history"] if h["action"] == "APPROVE"][0]
    assert manual_history["action_source"] == "MANUAL_REVIEW_CONSOLE"
    assert manual_history["notes"] == "Verified KYC documents and user phone verification."
    assert manual_history["reason"] == "KYC_VERIFIED"


def test_manual_review_invalid_action(client):
    """Invalid action string rejected with 422 validation error."""
    response = client.post(
        "/api/v1/review/tx_any/action",
        json={"action": "INVALID_DECISION"}
    )
    assert response.status_code == 422


def test_manual_review_nonexistent_transaction(client):
    """Action for nonexistent transaction returns 404."""
    response = client.post(
        "/api/v1/review/nonexistent_tx_000/action",
        json={"action": "APPROVE"}
    )
    assert response.status_code == 404


# =====================================================================
# 4. MODEL PERFORMANCE METRICS TESTS
# =====================================================================
def test_model_metrics_verified_benchmark_values(client):
    """
    GET /api/v1/model/metrics must return verified offline benchmark metrics,
    clearly labeled as offline evaluation on ULB dataset.
    """
    response = client.get("/api/v1/model/metrics")
    assert response.status_code == 200
    data = response.json()

    # Exact verified offline benchmark metrics
    assert data["evaluation_type"] == "OFFLINE BENCHMARK EVALUATION"
    assert data["dataset"] == "ULB Credit Card Fraud Detection"
    assert data["pr_auc"] == 0.7866
    assert data["roc_auc"] == 0.9595
    assert data["precision"] == 0.9342
    assert data["recall"] == 0.7474
    assert data["f1"] == 0.8304
    assert data["operating_threshold"] == 0.34
    assert data["fraud_prevalence_pct"] == 0.172749
    assert data["confusion_matrix"]["true_positives"] == 71
    assert data["confusion_matrix"]["false_positives"] == 5
    assert data["confusion_matrix"]["true_negatives"] == 56646
    assert data["confusion_matrix"]["false_negatives"] == 24
    assert "offline held-out test evaluation" in data["disclaimer"]
    assert "NOT represent live Razorpay" in data["disclaimer"]


def test_manual_ml_feature_vector_scoring_and_audit_integration(client):
    """
    Score valid manual benchmark feature vectors through POST /api/v1/risk/score
    and verify they produce their expected deterministic decisions and audit entries.
    """
    # 1. Low risk legitimate vector -> LOW tier, APPROVE
    t1_payload = sample_benchmark_payload(fraud_tendency=False, transaction_id="test_manual_legit_01")
    r1 = client.post("/api/v1/risk/score", json=t1_payload)
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["risk_tier"] == "LOW"
    assert d1["recommended_action"] == "APPROVE"
    assert d1["fraud_probability"] < 0.12

    # 2. Elevated fraud tendency vector -> HIGH/CRITICAL tier, REVIEW/BLOCK
    t2_payload = sample_benchmark_payload(fraud_tendency=True, transaction_id="test_manual_critical_02")
    r2 = client.post("/api/v1/risk/score", json=t2_payload)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["risk_tier"] in ("HIGH", "CRITICAL")
    assert d2["recommended_action"] in ("REVIEW", "BLOCK")


    # Verify both appear in audit logs
    audit_resp = client.get("/api/v1/audit/logs")
    assert audit_resp.status_code == 200
    logged_txns = [item["transaction_id"] for item in audit_resp.json()["items"]]
    assert "test_manual_legit_01" in logged_txns
    assert "test_manual_critical_02" in logged_txns


# =====================================================================
# 5. AUDIT LOGS TESTS
# =====================================================================

def test_audit_logs_empty_db(client):
    """Audit logs query on empty DB returns total=0 and items=[]."""
    response = client.get("/api/v1/audit/logs")
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []


def test_audit_logs_populated_and_filtering(client):
    """Audit logs can be filtered by event_type and action."""
    # Score a low-risk transaction
    t1 = sample_benchmark_payload(fraud_tendency=False)
    client.post("/api/v1/risk/score", json=t1)

    r_all = client.get("/api/v1/audit/logs")
    assert r_all.status_code == 200
    assert r_all.json()["total"] >= 1

    r_filter = client.get("/api/v1/audit/logs?event_type=INTERNAL_RISK_SCORE&action=APPROVE")
    assert r_filter.status_code == 200
    assert r_filter.json()["total"] >= 1
    assert r_filter.json()["items"][0]["action"] == "APPROVE"


# =====================================================================
# 6. SYSTEM STATUS TESTS
# =====================================================================
def test_system_status_operational(client):
    """System status returns verified operational indicators without claiming external connectivity."""
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("operational", "degraded")
    assert data["api"]["status"] == "healthy"
    assert data["api"]["service"] == "RazorRisk API"
    assert data["storage"]["status"] == "connected"
    assert data["model"]["status"] == "loaded"
    assert data["razorpay_integration"]["mode"] == "TEST_MODE"
    # Verification that only configuration booleans are exposed
    assert isinstance(data["razorpay_integration"]["key_id_configured"], bool)
    assert isinstance(data["razorpay_integration"]["key_secret_configured"], bool)
    assert isinstance(data["razorpay_integration"]["webhook_secret_configured"], bool)


# =====================================================================
# 7. SECURITY & SECRETS LEAK PREVENTION TEST
# =====================================================================
def test_secrets_never_returned_in_dashboard_endpoints(client):
    """Secrets must never be returned across any of the new dashboard endpoints."""
    settings = get_settings()
    secret1 = settings.RAZORPAY_KEY_SECRET
    secret2 = settings.RAZORPAY_WEBHOOK_SECRET

    endpoints = [
        "/api/v1/analytics/overview",
        "/api/v1/transactions",
        "/api/v1/review/queue",
        "/api/v1/model/metrics",
        "/api/v1/model/live-distribution",
        "/api/v1/model/offline-coverage",
        "/api/v1/audit/logs",
        "/api/v1/system/status"
    ]

    for ep in endpoints:
        res = client.get(ep)
        assert secret1 not in res.text, f"Secret leaked in {ep}"
        assert secret2 not in res.text, f"Secret leaked in {ep}"


# =====================================================================
# 8. RISK DISTRIBUTION & OFFLINE COVERAGE TESTS
# =====================================================================
def test_live_risk_distribution_api(client):
    """Test live risk distribution calculation on empty and populated data."""
    res = client.get("/api/v1/model/live-distribution")
    assert res.status_code == 200
    data = res.json()
    assert "total_native_scored" in data
    assert "tier_distribution" in data
    assert "LOW" in data["tier_distribution"]
    assert "MEDIUM" in data["tier_distribution"]
    assert "HIGH" in data["tier_distribution"]
    assert "CRITICAL" in data["tier_distribution"]
    assert "feature_space_diagnosis" in data


def test_offline_risk_coverage_api(client):
    """Test offline risk coverage endpoint returns real tier examples."""
    res = client.get("/api/v1/model/offline-coverage")
    assert res.status_code == 200
    data = res.json()
    assert data["evaluation_type"] == "OFFLINE_MODEL_RISK_COVERAGE"
    assert "tier_examples" in data
    assert "LOW" in data["tier_examples"]
    assert "MEDIUM" in data["tier_examples"]
    assert "HIGH" in data["tier_examples"]
    assert "CRITICAL" in data["tier_examples"]
    assert data["tier_examples"]["HIGH"]["risk_tier"] == "HIGH"
    assert data["tier_examples"]["CRITICAL"]["risk_tier"] == "CRITICAL"
    assert data["tier_examples"]["HIGH"]["fraud_probability"] >= 0.34
    assert data["tier_examples"]["CRITICAL"]["fraud_probability"] >= 0.80


# =====================================================================
# 9. MODEL EVALUATION QUEUE TESTS
# =====================================================================
def test_evaluation_queue_api(client):
    """GET /api/v1/review/evaluation-queue must return the 3 genuine held-out evaluation cases."""
    res = client.get("/api/v1/review/evaluation-queue")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    assert "disclaimer" in data

    ids = [it["eval_id"] for it in data["items"]]
    assert "EVAL-IEEE-00048" in ids
    assert "EVAL-IEEE-07876" in ids
    assert "EVAL-IEEE-01069" in ids

    # Check MEDIUM case
    med = next(it for it in data["items"] if it["eval_id"] == "EVAL-IEEE-00048")
    assert med["risk_tier"] == "MEDIUM"
    assert med["ai_recommendation"] == "REVIEW"
    assert abs(med["risk_score"] - 0.1691) < 0.001
    assert med["is_offline_eval"] is True

    # Check HIGH case
    high = next(it for it in data["items"] if it["eval_id"] == "EVAL-IEEE-07876")
    assert high["risk_tier"] == "HIGH"
    assert high["ai_recommendation"] == "BLOCK"
    assert abs(high["risk_score"] - 0.7562) < 0.001

    # Check CRITICAL case
    crit = next(it for it in data["items"] if it["eval_id"] == "EVAL-IEEE-01069")
    assert crit["risk_tier"] == "CRITICAL"
    assert crit["ai_recommendation"] == "BLOCK"
    assert abs(crit["risk_score"] - 1.0000) < 0.001


def test_evaluation_queue_analyst_action_creates_immutable_audit(client):
    """Analyst review action on evaluation case creates separate audit log while keeping automated score immutable."""
    settings = get_settings()
    store = AuditStore(settings.SQLITE_DB_PATH)

    # Confirm block on EVAL-IEEE-07876
    res = client.post(
        "/api/v1/review/EVAL-IEEE-07876/action",
        json={
            "action": "BLOCK",
            "notes": "Analyst verified high-velocity credential attack pattern.",
            "reason": "HIGH_VELOCITY_CONFIRMED"
        }
    )
    assert res.status_code == 200
    act_data = res.json()
    assert act_data["success"] is True
    assert act_data["transaction_id"] == "EVAL-IEEE-07876"
    assert act_data["new_action"] == "BLOCK"

    # Verify evaluation queue reflects human decision
    q_res = client.get("/api/v1/review/evaluation-queue")
    high_case = next(it for it in q_res.json()["items"] if it["eval_id"] == "EVAL-IEEE-07876")
    assert high_case["human_decision"] == "BLOCK"
    assert "CONFIRMED" in high_case["status_label"]
    assert abs(high_case["risk_score"] - 0.7562) < 0.001  # Original score untouched

    # Verify audit trail has both events: OFFLINE_EVALUATION_SCORED and MANUAL_REVIEW_DECISION
    audit_res = store.get_audit_logs(transaction_id="EVAL-IEEE-07876")
    assert audit_res["total"] == 2
    event_types = [it["event_type"] for it in audit_res["items"]]
    assert "OFFLINE_EVALUATION_SCORED" in event_types
    assert "MANUAL_REVIEW_DECISION" in event_types

