"""Asymmetric Business Cost Model for RazorRisk Policy Optimization."""

from typing import Dict, Tuple
from razorrisk.engine.types import CostProfile, CostProfileName, Action


def get_default_cost_profiles() -> Dict[CostProfileName, CostProfile]:
    """Factory returning the standard project cost profiles based on experimental assumptions."""
    return {
        CostProfileName.FRAUD_PREVENTION: CostProfile(
            name=CostProfileName.FRAUD_PREVENTION,
            description="Aggressive fraud interception. Minimizes chargeback losses at the cost of higher analyst review volume.",
            operational_threshold_review=0.08,
            operational_threshold_block=0.25,
            review_cost=10.0,
            chargeback_fee=15.0,
            false_positive_friction_cost=25.0,
            review_accuracy=0.95
        ),
        CostProfileName.BALANCED: CostProfile(
            name=CostProfileName.BALANCED,
            description="Balanced risk posture. Optimizes net composite business loss and F1 operational efficiency.",
            operational_threshold_review=0.12,
            operational_threshold_block=0.34,
            review_cost=35.0,
            chargeback_fee=15.0,
            false_positive_friction_cost=50.0,
            review_accuracy=0.92
        ),
        CostProfileName.CUSTOMER_EXPERIENCE: CostProfile(
            name=CostProfileName.CUSTOMER_EXPERIENCE,
            description="Low-friction user experience. High penalty for declining legitimate users; strict blocking criteria.",
            operational_threshold_review=0.18,
            operational_threshold_block=0.45,
            review_cost=75.0,
            chargeback_fee=15.0,
            false_positive_friction_cost=100.0,
            review_accuracy=0.90
        )
    }


def compute_expected_losses(
    fraud_prob: float,
    amount: float,
    profile: CostProfile
) -> Dict[Action, float]:
    """
    Calculate the mathematically expected financial loss for every candidate action.
    
    Formulas:
    1. E[Loss | APPROVE] = P(Fraud) * (Amount + Chargeback_Fee)
    2. E[Loss | BLOCK]   = (1 - P(Fraud)) * False_Positive_Friction_Cost
    3. E[Loss | REVIEW]  = Review_Cost + P(Fraud) * (1 - Review_Accuracy) * (Amount + Chargeback_Fee)
                          + (1 - P(Fraud)) * (1 - Review_Accuracy) * False_Positive_Friction_Cost
    """
    p_fraud = max(0.0, min(1.0, fraud_prob))
    p_legit = 1.0 - p_fraud
    amt = max(0.0, amount)

    # 1. Loss if Approved
    # If fraudulent: Merchant loses transaction amount + statutory chargeback dispute fee
    loss_if_fraud_approved = amt + profile.chargeback_fee
    expected_approve_loss = p_fraud * loss_if_fraud_approved

    # 2. Loss if Blocked
    # If legitimate: Merchant incurs customer friction, brand damage, and potential churn penalty
    expected_block_loss = p_legit * profile.false_positive_friction_cost

    # 3. Loss if Sent to Human Review
    # Incurs base manual review operational cost + residual error rate from review mistakes
    review_mistake_rate = 1.0 - profile.review_accuracy
    residual_fraud_leak = p_fraud * review_mistake_rate * loss_if_fraud_approved
    residual_friction = p_legit * review_mistake_rate * profile.false_positive_friction_cost
    expected_review_loss = profile.review_cost + residual_fraud_leak + residual_friction

    return {
        Action.APPROVE: round(expected_approve_loss, 2),
        Action.REVIEW: round(expected_review_loss, 2),
        Action.BLOCK: round(expected_block_loss, 2)
    }


def calculate_action_expected_loss(
    action: Action,
    fraud_prob: float,
    amount: float,
    profile: CostProfile
) -> float:
    """Calculate the expected loss for the specific action chosen by the policy engine."""
    all_losses = compute_expected_losses(fraud_prob, amount, profile)
    return all_losses[action]
