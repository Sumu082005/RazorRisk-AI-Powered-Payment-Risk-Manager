"""Comprehensive Path Verification and Regression Suite for RazorRisk Decision Engine.

Validates all 6 core decision pathways, boundary transitions, epistemic uncertainty downgrades,
fail-closed safety gates, and webhook pipeline separation.
"""

import math
import pytest
from razorrisk.engine.types import (
    ModelEvidence, CostProfileName, Action, RiskTier, ConfidenceTier
)
from razorrisk.engine.policy_engine import RiskDecisionEngine
from app.services.webhook_service import WebhookService
from app.storage.audit_store import AuditStore


class TestDecisionEnginePaths:
    """Rigorous path verification for every operational decision state."""

    @pytest.fixture(autouse=True)
    def setup_engine(self):
        self.engine = RiskDecisionEngine()

    # =========================================================================
    # PATH 1: LOW Risk -> Automated APPROVE
    # =========================================================================
    @pytest.mark.parametrize("prob,expected_loss_cap", [
        (0.0001, 1.0),
        (0.015, 5.0),
        (0.080, 10.0),
        (0.099, 15.0),
    ])
    def test_path_1_low_risk_automated_approve(self, prob, expected_loss_cap):
        """Probability < 0.10 with standard confidence must produce LOW / APPROVE."""
        evidence = ModelEvidence(
            transaction_id="tx_low_verify",
            transaction_amount=50.0,
            fraud_probability=prob,
            calibrated_probability=prob,
            tree_dispersion_std=0.03
        )
        decision = self.engine.evaluate(evidence, profile_name=CostProfileName.BALANCED)

        assert decision.recommended_action == Action.APPROVE
        assert decision.risk_tier == RiskTier.LOW
        assert decision.requires_human_review is False
        assert any(r.rule_id == "POL-03-LOW-RISK-APPROVE" for r in decision.triggered_rules)
        assert decision.estimated_expected_loss <= expected_loss_cap

    # =========================================================================
    # PATH 2: MEDIUM Risk -> REVIEW
    # =========================================================================
    @pytest.mark.parametrize("prob", [0.12, 0.15, 0.22, 0.30, 0.339])
    def test_path_2_medium_risk_routes_to_review(self, prob):
        """Probability in [0.12, 0.34) must produce MEDIUM / REVIEW."""
        evidence = ModelEvidence(
            transaction_id="tx_med_verify",
            transaction_amount=100.0,
            fraud_probability=prob,
            calibrated_probability=prob,
            tree_dispersion_std=0.08
        )
        decision = self.engine.evaluate(evidence, profile_name=CostProfileName.BALANCED)

        assert decision.recommended_action == Action.REVIEW
        assert decision.risk_tier == RiskTier.MEDIUM
        assert decision.requires_human_review is True
        assert any(r.rule_id == "POL-02-REVIEW-THRESHOLD" for r in decision.triggered_rules)

    # =========================================================================
    # PATH 3: HIGH Risk (High Confidence) -> Automated BLOCK
    # =========================================================================
    @pytest.mark.parametrize("prob", [0.55, 0.65, 0.72, 0.78])
    def test_path_3_high_risk_high_confidence_block(self, prob):
        """Probability in [0.34, 0.80) with high confidence (far from boundary, tight calibration) must BLOCK."""
        evidence = ModelEvidence(
            transaction_id="tx_high_verify",
            transaction_amount=250.0,
            fraud_probability=prob,
            calibrated_probability=prob,  # No calibration discrepancy
            tree_dispersion_std=0.04       # Low tree variance (< 0.38)
        )
        decision = self.engine.evaluate(evidence, profile_name=CostProfileName.BALANCED)

        assert decision.recommended_action == Action.BLOCK
        assert decision.risk_tier == RiskTier.HIGH
        assert decision.confidence_tier == ConfidenceTier.HIGH_CONFIDENCE
        assert decision.requires_human_review is False
        assert any(r.rule_id == "POL-01-BLOCK-THRESHOLD" for r in decision.triggered_rules)

    # =========================================================================
    # PATH 4: CRITICAL Risk (>= 0.80) -> Hard-Stop BLOCK
    # =========================================================================
    @pytest.mark.parametrize("prob,tree_std", [
        (0.80, 0.05),
        (0.85, 0.45),  # High uncertainty must NOT prevent hard block
        (0.92, 0.48),
        (1.00, 0.00)
    ])
    def test_path_4_critical_risk_hard_stop_block(self, prob, tree_std):
        """Probability >= 0.80 must trigger SAFE-07-CRITICAL-FRAUD-LOCK and unconditionally BLOCK."""
        evidence = ModelEvidence(
            transaction_id="tx_crit_verify",
            transaction_amount=500.0,
            fraud_probability=prob,
            calibrated_probability=prob,
            tree_dispersion_std=tree_std
        )
        decision = self.engine.evaluate(evidence, profile_name=CostProfileName.BALANCED)

        assert decision.recommended_action == Action.BLOCK
        assert decision.risk_tier == RiskTier.CRITICAL
        assert any(r.rule_id == "SAFE-07-CRITICAL-FRAUD-LOCK" for r in decision.triggered_rules)
        # Verify SAFE-08 uncertainty downgrade is NEVER applied to critical tier
        assert not any(r.rule_id == "SAFE-08-UNCERTAINTY-DOWNGRADE" for r in decision.triggered_rules)

    # =========================================================================
    # PATH 5: LOW Confidence Epistemic Downgrade -> REVIEW
    # =========================================================================
    def test_path_5_low_confidence_near_boundary_downgrade(self):
        """Probability in block zone (0.35) near boundary (0.34 +/- 0.05) must downgrade to REVIEW."""
        evidence = ModelEvidence(
            transaction_id="tx_uncert_boundary",
            transaction_amount=200.0,
            fraud_probability=0.35,  # Within 0.05 ambiguity band
            calibrated_probability=0.35,
            tree_dispersion_std=0.10
        )
        decision = self.engine.evaluate(evidence, profile_name=CostProfileName.BALANCED)

        assert decision.risk_tier == RiskTier.HIGH
        assert decision.confidence_tier == ConfidenceTier.LOW_CONFIDENCE
        assert decision.recommended_action == Action.REVIEW
        assert any(r.rule_id == "SAFE-08-UNCERTAINTY-DOWNGRADE" for r in decision.triggered_rules)

    def test_path_5_low_confidence_high_dispersion_downgrade(self):
        """Probability = 0.65 with high tree dispersion (std >= 0.38) must downgrade to REVIEW."""
        evidence = ModelEvidence(
            transaction_id="tx_uncert_dispersion",
            transaction_amount=200.0,
            fraud_probability=0.65,
            calibrated_probability=0.65,
            tree_dispersion_std=0.42  # High dispersion trigger (>= 0.38)
        )
        decision = self.engine.evaluate(evidence, profile_name=CostProfileName.BALANCED)

        assert decision.risk_tier == RiskTier.HIGH
        assert decision.confidence_tier == ConfidenceTier.LOW_CONFIDENCE
        assert decision.recommended_action == Action.REVIEW
        assert any(r.rule_id == "SAFE-08-UNCERTAINTY-DOWNGRADE" for r in decision.triggered_rules)

    def test_path_5_low_confidence_calibration_divergence_downgrade(self):
        """Probability = 0.60 with high calibration gap (|0.60 - 0.35| >= 0.15) must downgrade to REVIEW."""
        evidence = ModelEvidence(
            transaction_id="tx_uncert_calib",
            transaction_amount=200.0,
            fraud_probability=0.60,
            calibrated_probability=0.35,  # Gap = 0.25 >= 0.15
            tree_dispersion_std=0.10
        )
        decision = self.engine.evaluate(evidence, profile_name=CostProfileName.BALANCED)

        assert decision.risk_tier == RiskTier.HIGH
        assert decision.confidence_tier == ConfidenceTier.LOW_CONFIDENCE
        assert decision.recommended_action == Action.REVIEW
        assert any(r.rule_id == "SAFE-08-UNCERTAINTY-DOWNGRADE" for r in decision.triggered_rules)

    # =========================================================================
    # PATH 6: MODEL_NOT_APPLICABLE (Razorpay Webhook) -> REVIEW
    # =========================================================================
    def test_path_6_razorpay_webhook_model_not_applicable(self, tmp_path):
        """Razorpay webhook lacking benchmark PCA features must safely route to REVIEW without ML scoring."""
        db_path = str(tmp_path / "test_audit.db")
        store = AuditStore(db_path)
        service = WebhookService(webhook_secret="test_secret_123", audit_store=store)

        import hmac, hashlib, json
        payload = {
            "entity": "event",
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_separation_01",
                        "amount": 5000,
                        "currency": "INR",
                        "status": "captured"
                    }
                }
            }
        }
        body = json.dumps(payload).encode("utf-8")
        sig = hmac.new(b"test_secret_123", body, hashlib.sha256).hexdigest()

        result = service.process_webhook(raw_body=body, signature=sig)

        assert result.action_taken == "REVIEW"
        assert result.processing_status == "MODEL_NOT_APPLICABLE"

        # Verify audit record integrity
        logs_resp = store.get_audit_logs(limit=10)
        items = logs_resp["items"]
        assert len(items) == 1
        log = items[0]
        assert log["action"] == "REVIEW"
        assert log["risk_score"] is None
        assert log["risk_tier"] == "MEDIUM"
        assert log["confidence_tier"] == "LOW_CONFIDENCE"
        assert log["details"]["schema_applicability"] == "BENCHMARK_PCA_FEATURES_NOT_PRESENT"
        assert log["details"]["safety_action"] == "ROUTED_TO_MANUAL_REVIEW"


    # =========================================================================
    # BOUNDARY TESTS (Threshold Transitions with Epsilon = 0.001)
    # =========================================================================
    def test_boundary_review_threshold_transition(self):
        """Test transitions around review threshold (0.12 in BALANCED)."""
        eps = 0.001

        # 1. Just below threshold (0.119) -> LOW risk tier, APPROVE action
        ev_below = ModelEvidence(transaction_id="b_rev_below", transaction_amount=50.0, fraud_probability=0.12 - eps)
        dec_below = self.engine.evaluate(ev_below)
        assert dec_below.recommended_action == Action.APPROVE
        assert dec_below.risk_tier == RiskTier.MEDIUM  # RiskTier.MEDIUM starts at 0.10

        # 2. Exactly at threshold (0.120) -> REVIEW
        ev_exact = ModelEvidence(transaction_id="b_rev_exact", transaction_amount=50.0, fraud_probability=0.12)
        dec_exact = self.engine.evaluate(ev_exact)
        assert dec_exact.recommended_action == Action.REVIEW
        assert dec_exact.risk_tier == RiskTier.MEDIUM

        # 3. Just above threshold (0.121) -> REVIEW
        ev_above = ModelEvidence(transaction_id="b_rev_above", transaction_amount=50.0, fraud_probability=0.12 + eps)
        dec_above = self.engine.evaluate(ev_above)
        assert dec_above.recommended_action == Action.REVIEW
        assert dec_above.risk_tier == RiskTier.MEDIUM

    def test_boundary_critical_threshold_transition(self):
        """Test transitions around critical risk threshold (0.80)."""
        eps = 0.001

        # 1. Just below critical (0.799) with low confidence -> downgraded to REVIEW
        ev_below = ModelEvidence(
            transaction_id="b_crit_below",
            transaction_amount=100.0,
            fraud_probability=0.80 - eps,
            calibrated_probability=0.80 - eps,
            tree_dispersion_std=0.40  # Low confidence trigger
        )
        dec_below = self.engine.evaluate(ev_below)
        assert dec_below.risk_tier == RiskTier.HIGH
        assert dec_below.recommended_action == Action.REVIEW  # Downgraded

        # 2. Exactly at critical (0.800) -> Hard BLOCK regardless of dispersion
        ev_exact = ModelEvidence(
            transaction_id="b_crit_exact",
            transaction_amount=100.0,
            fraud_probability=0.80,
            calibrated_probability=0.80,
            tree_dispersion_std=0.40
        )
        dec_exact = self.engine.evaluate(ev_exact)
        assert dec_exact.risk_tier == RiskTier.CRITICAL
        assert dec_exact.recommended_action == Action.BLOCK  # Hard lock

        # 3. Just above critical (0.801) -> Hard BLOCK
        ev_above = ModelEvidence(
            transaction_id="b_crit_above",
            transaction_amount=100.0,
            fraud_probability=0.80 + eps,
            calibrated_probability=0.80 + eps,
            tree_dispersion_std=0.40
        )
        dec_above = self.engine.evaluate(ev_above)
        assert dec_above.risk_tier == RiskTier.CRITICAL
        assert dec_above.recommended_action == Action.BLOCK

    # =========================================================================
    # INVALID MODEL OUTPUTS (Fail-Closed Safety Gate)
    # =========================================================================
    @pytest.mark.parametrize("invalid_prob,rule_id", [
        (-0.01, "SAFE-02-OUT-OF-BOUNDS-PROB"),
        (-1.00, "SAFE-02-OUT-OF-BOUNDS-PROB"),
        (1.001, "SAFE-02-OUT-OF-BOUNDS-PROB"),
        (2.50, "SAFE-02-OUT-OF-BOUNDS-PROB"),
        (float("nan"), "SAFE-01-MALFORMED-PROB"),
        (float("inf"), "SAFE-01-MALFORMED-PROB"),
        (float("-inf"), "SAFE-01-MALFORMED-PROB"),
    ])
    def test_invalid_probability_fails_closed(self, invalid_prob, rule_id):
        """Out-of-bounds or NaN/Inf probability must fail-closed to REVIEW and never approve/block."""
        evidence = ModelEvidence(
            transaction_id="tx_inv_prob",
            transaction_amount=50.0,
            fraud_probability=invalid_prob
        )
        decision = self.engine.evaluate(evidence)

        assert decision.recommended_action == Action.REVIEW
        assert decision.requires_human_review is True
        assert any(r.rule_id == rule_id for r in decision.triggered_rules)
        assert decision.audit_event["execution_status"] == "FAIL_CLOSED"

    @pytest.mark.parametrize("invalid_amount,rule_id", [
        (-0.01, "SAFE-04-NEGATIVE-AMOUNT"),
        (-100.0, "SAFE-04-NEGATIVE-AMOUNT"),
        (float("nan"), "SAFE-03-MALFORMED-AMOUNT"),
        (float("inf"), "SAFE-03-MALFORMED-AMOUNT"),
    ])
    def test_invalid_amount_fails_closed(self, invalid_amount, rule_id):
        """Negative or NaN/Inf transaction amount must fail-closed to REVIEW."""
        evidence = ModelEvidence(
            transaction_id="tx_inv_amt",
            transaction_amount=invalid_amount,
            fraud_probability=0.05
        )
        decision = self.engine.evaluate(evidence)

        assert decision.recommended_action == Action.REVIEW
        assert decision.requires_human_review is True
        assert any(r.rule_id == rule_id for r in decision.triggered_rules)
        assert decision.audit_event["execution_status"] == "FAIL_CLOSED"

    # =========================================================================
    # MEDIUM TIER VS ACTION THRESHOLD CLARIFICATION (0.099 - 0.121)
    # =========================================================================
    @pytest.mark.parametrize("prob,expected_tier,expected_action,expected_rule", [
        (0.099, RiskTier.LOW, Action.APPROVE, "POL-03-LOW-RISK-APPROVE"),
        (0.100, RiskTier.MEDIUM, Action.APPROVE, "POL-03-LOW-RISK-APPROVE"),
        (0.105, RiskTier.MEDIUM, Action.APPROVE, "POL-03-LOW-RISK-APPROVE"),
        (0.110, RiskTier.MEDIUM, Action.APPROVE, "POL-03-LOW-RISK-APPROVE"),
        (0.119, RiskTier.MEDIUM, Action.APPROVE, "POL-03-LOW-RISK-APPROVE"),
        (0.120, RiskTier.MEDIUM, Action.REVIEW, "POL-02-REVIEW-THRESHOLD"),
        (0.121, RiskTier.MEDIUM, Action.REVIEW, "POL-02-REVIEW-THRESHOLD"),
    ])
    def test_medium_tier_and_action_threshold_boundary_clarification(self, prob, expected_tier, expected_action, expected_rule):
        """
        Clarify the architectural separation:
        - RiskTier (taxonomy): LOW is < 0.10, MEDIUM is 0.10 <= p < 0.34
        - Cost Profile (BALANCED action): APPROVE is p < 0.12, REVIEW is p >= 0.12
        Therefore, p in [0.100, 0.119] is MEDIUM RISK + APPROVE under BALANCED posture.
        """
        evidence = ModelEvidence(
            transaction_id=f"tx_boundary_{prob}",
            transaction_amount=50.0,
            fraud_probability=prob,
            calibrated_probability=prob,
            tree_dispersion_std=0.03
        )
        decision = self.engine.evaluate(evidence, profile_name=CostProfileName.BALANCED)

        assert decision.risk_tier == expected_tier
        assert decision.recommended_action == expected_action
        assert any(r.rule_id == expected_rule for r in decision.triggered_rules)

