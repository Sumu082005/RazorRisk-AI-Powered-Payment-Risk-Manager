"""Deterministic Policy Rules, Safety Gates, and Input Boundary Validators."""

import math
from typing import List, Tuple, Optional
from razorrisk.engine.types import (
    ModelEvidence, CostProfile, Action, RiskTier, ConfidenceTier, TriggeredRule
)


def validate_input_boundaries(evidence: ModelEvidence) -> Tuple[bool, List[TriggeredRule]]:
    """
    Strict boundary check for numerical integrity and missing/malformed values.
    Returns (is_valid, list_of_safety_rules).
    """
    safety_rules = []
    is_valid = True
    
    # 1. Check fraud probability
    p = evidence.fraud_probability
    if p is None or math.isnan(p) or math.isinf(p):
        is_valid = False
        safety_rules.append(TriggeredRule(
            rule_id="SAFE-01-MALFORMED-PROB",
            rule_name="Malformed Risk Probability",
            severity="CRITICAL",
            description=f"Model output probability is invalid ({p}). Failing closed to manual investigation.",
            action_impact=Action.REVIEW
        ))
    elif p < 0.0 or p > 1.0:
        is_valid = False
        safety_rules.append(TriggeredRule(
            rule_id="SAFE-02-OUT-OF-BOUNDS-PROB",
            rule_name="Out-of-Bounds Probability",
            severity="CRITICAL",
            description=f"Probability {p} is outside the valid mathematical domain [0.0, 1.0]. Failing closed.",
            action_impact=Action.REVIEW
        ))
        
    # 2. Check transaction amount
    amt = evidence.transaction_amount
    if amt is None or math.isnan(amt) or math.isinf(amt):
        is_valid = False
        safety_rules.append(TriggeredRule(
            rule_id="SAFE-03-MALFORMED-AMOUNT",
            rule_name="Malformed Transaction Amount",
            severity="CRITICAL",
            description=f"Transaction amount is invalid ({amt}). Failing closed.",
            action_impact=Action.REVIEW
        ))
    elif amt < 0.0:
        is_valid = False
        safety_rules.append(TriggeredRule(
            rule_id="SAFE-04-NEGATIVE-AMOUNT",
            rule_name="Negative Transaction Amount",
            severity="CRITICAL",
            description=f"Transaction amount cannot be negative (${amt:.2f}). Failing closed.",
            action_impact=Action.REVIEW
        ))
        
    return is_valid, safety_rules


def determine_risk_tier(fraud_prob: float, block_threshold: float = 0.34) -> RiskTier:
    """Classify the continuous fraud probability into an operational Risk Tier."""
    p = max(0.0, min(1.0, fraud_prob))
    
    if p >= 0.80:
        return RiskTier.CRITICAL
    elif p >= block_threshold:
        return RiskTier.HIGH
    elif p >= 0.10:
        return RiskTier.MEDIUM
    else:
        return RiskTier.LOW


def evaluate_policy_rules(
    evidence: ModelEvidence,
    cost_profile: CostProfile,
    risk_tier: RiskTier,
    confidence_tier: ConfidenceTier
) -> Tuple[Action, List[TriggeredRule], bool]:
    """
    Execute deterministic decision gates combining model risk, confidence, cost posture, and safety constraints.
    Returns (final_action, triggered_rules, requires_human_review).
    """
    rules: List[TriggeredRule] = []
    p = evidence.fraud_probability
    amt = evidence.transaction_amount
    t_block = cost_profile.operational_threshold_block
    t_review = cost_profile.operational_threshold_review
    
    # 1. Base Cost-Profile Action Resolution
    if p >= t_block:
        action = Action.BLOCK
        rules.append(TriggeredRule(
            rule_id="POL-01-BLOCK-THRESHOLD",
            rule_name="Cost Profile Block Threshold Exceeded",
            severity="HIGH",
            description=f"Fraud probability ({p:.4f}) meets or exceeds {cost_profile.name.value} block threshold ({t_block:.2f}).",
            action_impact=Action.BLOCK
        ))
    elif p >= t_review:
        action = Action.REVIEW
        rules.append(TriggeredRule(
            rule_id="POL-02-REVIEW-THRESHOLD",
            rule_name="Elevated Risk Requiring Review",
            severity="MEDIUM",
            description=f"Fraud probability ({p:.4f}) exceeds review threshold ({t_review:.2f}) in {cost_profile.name.value} posture.",
            action_impact=Action.REVIEW
        ))
    else:
        action = Action.APPROVE
        rules.append(TriggeredRule(
            rule_id="POL-03-LOW-RISK-APPROVE",
            rule_name="Standard Low Risk Approval",
            severity="INFO",
            description=f"Fraud probability ({p:.4f}) is below review threshold ({t_review:.2f}).",
            action_impact=Action.APPROVE
        ))

    # 2. Safety Gate: Zero-Amount Probe (Auth Check)
    if amt == 0.0 and p >= 0.05:
        if action == Action.APPROVE:
            action = Action.REVIEW
            rules.append(TriggeredRule(
                rule_id="SAFE-05-ZERO-AMOUNT-PROBE",
                rule_name="Zero-Amount Authorization Check",
                severity="MEDIUM",
                description="Zero-dollar authorization check with elevated anomaly score. Routing to review.",
                action_impact=Action.REVIEW
            ))

    # 3. Safety Gate: High-Value Exposure Gate ($10,000+)
    if amt >= 10000.0 and p >= 0.10:
        if action == Action.APPROVE:
            action = Action.REVIEW
            rules.append(TriggeredRule(
                rule_id="SAFE-06-HIGH-EXPOSURE-AMOUNT",
                rule_name="High-Value Financial Exposure Gate",
                severity="HIGH",
                description=f"Transaction amount (${amt:,.2f}) exceeds high-exposure threshold with non-zero risk score ({p:.4f}).",
                action_impact=Action.REVIEW
            ))

    # 4. Critical Risk Override: High Probability Hard Block (>= 0.80)
    if p >= 0.80:
        action = Action.BLOCK
        rules.append(TriggeredRule(
            rule_id="SAFE-07-CRITICAL-FRAUD-LOCK",
            rule_name="Critical Fraud Risk Automatic Block",
            severity="CRITICAL",
            description=f"Transaction probability ({p:.4f}) meets Critical Risk Tier (>= 0.80). Enforcing immediate block.",
            action_impact=Action.BLOCK
        ))

    # 5. Epistemic Confidence Gate: Downgrade Uncertain Blocks to Human Review
    # Exception: Do not downgrade Critical Tier (>= 0.80)
    if action == Action.BLOCK and confidence_tier == ConfidenceTier.LOW_CONFIDENCE and p < 0.80:
        action = Action.REVIEW
        rules.append(TriggeredRule(
            rule_id="SAFE-08-UNCERTAINTY-DOWNGRADE",
            rule_name="Low Confidence Block Downgraded to Review",
            severity="WARNING",
            description=f"Block action downgraded to REVIEW because model confidence is LOW near decision boundary ({p:.4f} vs threshold {t_block:.2f}).",
            action_impact=Action.REVIEW
        ))

    requires_review = (action == Action.REVIEW)
    return action, rules, requires_review
