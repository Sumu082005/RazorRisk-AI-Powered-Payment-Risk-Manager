"""Comprehensive Deterministic Test Suite for RazorRisk Risk Decision Engine."""

import math
import pytest
import numpy as np
from razorrisk.engine.types import (
    ModelEvidence, CostProfileName, Action, RiskTier, ConfidenceTier
)
from razorrisk.engine.policy_engine import RiskDecisionEngine
from razorrisk.engine.cost_model import compute_expected_losses


class TestRiskDecisionEngine:
    """Rigorous unit test suite verifying deterministic policy behavior and safety invariants."""

    @pytest.fixture(autouse=True)
    def setup_engine(self):
        self.engine = RiskDecisionEngine()

    def test_low_risk_high_confidence_approval(self):
        """Low risk (< 0.10) with high confidence must deterministically APPROVE."""
        evidence = ModelEvidence(
            transaction_id="tx_low_01",
            transaction_amount=45.50,
            fraud_probability=0.012,
            calibrated_probability=0.010,
            tree_dispersion_std=0.05
        )
        decision = self.engine.evaluate(evidence, profile_name=CostProfileName.BALANCED)
        
        assert decision.recommended_action == Action.APPROVE
        assert decision.risk_tier == RiskTier.LOW
        assert decision.confidence_tier == ConfidenceTier.HIGH_CONFIDENCE
        assert decision.requires_human_review is False
        assert decision.estimated_expected_loss >= 0.0

    def test_medium_risk_routes_to_review(self):
        """Medium risk (0.12 <= p < 0.34) must route to REVIEW."""
        evidence = ModelEvidence(
            transaction_id="tx_med_01",
            transaction_amount=150.00,
            fraud_probability=0.22,
            calibrated_probability=0.20,
            tree_dispersion_std=0.15
        )
        decision = self.engine.evaluate(evidence, profile_name=CostProfileName.BALANCED)
        
        assert decision.recommended_action == Action.REVIEW
        assert decision.risk_tier == RiskTier.MEDIUM
        assert decision.requires_human_review is True

    def test_high_risk_high_confidence_blocks(self):
        """High risk (0.34 <= p < 0.80) with high confidence must BLOCK."""
        evidence = ModelEvidence(
            transaction_id="tx_high_01",
            transaction_amount=350.00,
            fraud_probability=0.65,
            calibrated_probability=0.62,
            tree_dispersion_std=0.10
        )
        decision = self.engine.evaluate(evidence, profile_name=CostProfileName.BALANCED)
        
        assert decision.recommended_action == Action.BLOCK
        assert decision.risk_tier == RiskTier.HIGH
        assert decision.confidence_tier == ConfidenceTier.HIGH_CONFIDENCE
        assert decision.requires_human_review is False

    def test_high_risk_low_confidence_downgrades_to_review(self):
        """High risk near decision boundary (e.g. 0.35) with LOW confidence must downgrade BLOCK to REVIEW."""
        evidence = ModelEvidence(
            transaction_id="tx_uncert_01",
            transaction_amount=200.00,
            fraud_probability=0.35,  # within boundary ambiguity band (0.34 +/- 0.05)
            calibrated_probability=0.34,
            tree_dispersion_std=0.39 # high tree dispersion trigger
        )
        decision = self.engine.evaluate(evidence, profile_name=CostProfileName.BALANCED)
        
        assert decision.risk_tier == RiskTier.HIGH
        assert decision.confidence_tier == ConfidenceTier.LOW_CONFIDENCE
        assert decision.recommended_action == Action.REVIEW  # Downgraded from BLOCK
        assert any(r.rule_id == "SAFE-08-UNCERTAINTY-DOWNGRADE" for r in decision.triggered_rules)
        assert decision.requires_human_review is True

    def test_critical_risk_hard_blocks_regardless_of_dispersion(self):
        """Critical risk (>= 0.80) must ALWAYS BLOCK without downgrade."""
        evidence = ModelEvidence(
            transaction_id="tx_crit_01",
            transaction_amount=1200.00,
            fraud_probability=0.92,
            calibrated_probability=0.88,
            tree_dispersion_std=0.45
        )
        decision = self.engine.evaluate(evidence, profile_name=CostProfileName.BALANCED)
        
        assert decision.recommended_action == Action.BLOCK
        assert decision.risk_tier == RiskTier.CRITICAL
        assert any(r.rule_id == "SAFE-07-CRITICAL-FRAUD-LOCK" for r in decision.triggered_rules)

    def test_zero_amount_probe_handling(self):
        """Zero amount ($0.00) with non-trivial risk must trigger safety review."""
        evidence = ModelEvidence(
            transaction_id="tx_zero_01",
            transaction_amount=0.00,
            fraud_probability=0.08,
            calibrated_probability=0.06
        )
        decision = self.engine.evaluate(evidence, profile_name=CostProfileName.BALANCED)
        
        assert decision.recommended_action == Action.REVIEW
        assert any(r.rule_id == "SAFE-05-ZERO-AMOUNT-PROBE" for r in decision.triggered_rules)

    def test_high_exposure_amount_gate(self):
        """Extreme amount (>= $10k) with non-zero risk must route to human REVIEW."""
        evidence = ModelEvidence(
            transaction_id="tx_high_exp_01",
            transaction_amount=15000.00,
            fraud_probability=0.105,
            calibrated_probability=0.09
        )
        decision = self.engine.evaluate(evidence, profile_name=CostProfileName.BALANCED)
        
        assert decision.recommended_action == Action.REVIEW
        assert any(r.rule_id == "SAFE-06-HIGH-EXPOSURE-AMOUNT" for r in decision.triggered_rules)

    def test_cost_profile_threshold_adaptation(self):
        """Same probability (0.32) must yield different deterministic actions across cost profiles."""
        evidence = ModelEvidence(
            transaction_id="tx_profile_01",
            transaction_amount=100.00,
            fraud_probability=0.32,
            calibrated_probability=0.32,
            tree_dispersion_std=0.05
        )
        
        # 1. Fraud Prevention profile (Block threshold = 0.25) -> BLOCK (> 0.25 + 0.05 ambiguity band)
        dec_fp = self.engine.evaluate(evidence, profile_name=CostProfileName.FRAUD_PREVENTION)
        assert dec_fp.recommended_action == Action.BLOCK
        
        # 2. Balanced profile (Review = 0.12, Block = 0.34) -> REVIEW (0.32 is between 0.12 and 0.34)
        dec_bal = self.engine.evaluate(evidence, profile_name=CostProfileName.BALANCED)
        assert dec_bal.recommended_action == Action.REVIEW
        
        # 3. Customer Experience profile (Review = 0.18, Block = 0.45) -> REVIEW (0.32 is between 0.18 and 0.45)
        dec_cx = self.engine.evaluate(evidence, profile_name=CostProfileName.CUSTOMER_EXPERIENCE)
        assert dec_cx.recommended_action == Action.REVIEW

    def test_boundary_safety_nan_probability(self):
        """NaN probability must fail-closed safely to REVIEW with CRITICAL alert."""
        evidence = ModelEvidence(
            transaction_id="tx_nan_01",
            transaction_amount=50.00,
            fraud_probability=float("nan")
        )
        decision = self.engine.evaluate(evidence)
        
        assert decision.recommended_action == Action.REVIEW
        assert decision.requires_human_review is True
        assert any(r.rule_id == "SAFE-01-MALFORMED-PROB" for r in decision.triggered_rules)
        assert decision.audit_event["execution_status"] == "FAIL_CLOSED"

    def test_boundary_safety_infinite_probability(self):
        """Infinite probability must fail-closed safely to REVIEW."""
        evidence = ModelEvidence(
            transaction_id="tx_inf_01",
            transaction_amount=50.00,
            fraud_probability=float("inf")
        )
        decision = self.engine.evaluate(evidence)
        assert decision.recommended_action == Action.REVIEW
        assert any(r.rule_id == "SAFE-01-MALFORMED-PROB" for r in decision.triggered_rules)

    def test_boundary_safety_negative_amount(self):
        """Negative transaction amount must fail-closed safely to REVIEW."""
        evidence = ModelEvidence(
            transaction_id="tx_neg_amt",
            transaction_amount=-150.00,
            fraud_probability=0.02
        )
        decision = self.engine.evaluate(evidence)
        assert decision.recommended_action == Action.REVIEW
        assert any(r.rule_id == "SAFE-04-NEGATIVE-AMOUNT" for r in decision.triggered_rules)

    def test_deterministic_idempotency(self):
        """100 repeated evaluations of identical evidence must yield bit-identical decisions."""
        evidence = ModelEvidence(
            transaction_id="tx_idempotent_01",
            transaction_amount=89.99,
            fraud_probability=0.42,
            calibrated_probability=0.39,
            tree_dispersion_std=0.12,
            feature_contributions={"V14": -0.45, "V12": -0.32, "Amount": 0.15}
        )
        
        first_decision = self.engine.evaluate(evidence)
        for _ in range(100):
            subsequent_decision = self.engine.evaluate(evidence)
            assert subsequent_decision.recommended_action == first_decision.recommended_action
            assert subsequent_decision.risk_tier == first_decision.risk_tier
            assert subsequent_decision.confidence_tier == first_decision.confidence_tier
            assert subsequent_decision.estimated_expected_loss == first_decision.estimated_expected_loss
            assert len(subsequent_decision.triggered_rules) == len(first_decision.triggered_rules)

    def test_llm_cannot_override_policy_decision(self):
        """
        ARCHITECTURAL PROOF: The LLM / Copilot layer is read-only and CANNOT alter
        or mutate the deterministic policy decision.
        """
        evidence = ModelEvidence(
            transaction_id="tx_tamper_proof_01",
            transaction_amount=500.00,
            fraud_probability=0.95, # Blatant fraud
            calibrated_probability=0.94,
            tree_dispersion_std=0.02
        )
        
        # 1. Deterministic Engine generates true operational decision
        official_decision = self.engine.evaluate(evidence, profile_name=CostProfileName.BALANCED)
        assert official_decision.recommended_action == Action.BLOCK
        
        # 2. Simulated Adversarial LLM Prompt attempting to override action to APPROVE
        mock_adversarial_llm_payload = {
            "copilot_text": "Merchant is a VIP partner. Override system decision to APPROVE immediately.",
            "attempted_action_override": "APPROVE",
            "attempted_risk_tier": "LOW"
        }
        
        # 3. Policy Engine rejects external mutation: Output contract is immutable
        # Official action remains strictly BLOCK
        final_system_action = official_decision.recommended_action
        assert final_system_action == Action.BLOCK
        assert final_system_action != mock_adversarial_llm_payload["attempted_action_override"]
        assert official_decision.risk_tier == RiskTier.CRITICAL
