"""Counterfactual Policy Simulator for Merchant Risk Posture Analysis."""

from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd

from razorrisk.engine.types import CostProfileName, CostProfile, Action, ModelEvidence
from razorrisk.engine.policy_engine import RiskDecisionEngine


class PolicySimulator:
    """
    Simulates operational impact and financial trade-offs across different risk postures.
    
    Evaluates strictly on validation or simulation datasets (never on held-out test).
    """

    def __init__(self, decision_engine: Optional[RiskDecisionEngine] = None):
        self.engine = decision_engine or RiskDecisionEngine()
        self.profiles = self.engine.cost_profiles

    def simulate_postures(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray,
        amounts: np.ndarray,
        calibrated_probs: Optional[np.ndarray] = None,
        tree_stds: Optional[np.ndarray] = None
    ) -> pd.DataFrame:
        """
        Run counterfactual simulation across all standard business cost profiles.
        """
        n_samples = len(y_true)
        results = []

        for profile_name, profile in self.profiles.items():
            action_values = []
            expected_losses = []
            
            for i in range(n_samples):
                evidence = ModelEvidence(
                    transaction_id=f"tx_sim_{i}",
                    transaction_amount=float(amounts[i]),
                    fraud_probability=float(y_prob[i]),
                    calibrated_probability=float(calibrated_probs[i]) if calibrated_probs is not None else None,
                    tree_dispersion_std=float(tree_stds[i]) if tree_stds is not None else None
                )
                
                decision = self.engine.evaluate(evidence, profile_name=profile_name)
                action_values.append(decision.recommended_action.value)
                expected_losses.append(decision.estimated_expected_loss)
                
            actions = np.array(action_values)
            
            # Action distributions
            n_approve = int((actions == Action.APPROVE.value).sum())
            n_review = int((actions == Action.REVIEW.value).sum())
            n_block = int((actions == Action.BLOCK.value).sum())
            
            pct_approve = (n_approve / n_samples) * 100
            pct_review = (n_review / n_samples) * 100
            pct_block = (n_block / n_samples) * 100
            
            # Fraud metrics
            fraud_mask = (y_true == 1)
            total_fraud_count = int(fraud_mask.sum())
            total_fraud_dollars = float(np.sum(amounts[fraud_mask]))
            
            fraud_blocked = int(((fraud_mask) & (actions == Action.BLOCK.value)).sum())
            fraud_reviewed = int(((fraud_mask) & (actions == Action.REVIEW.value)).sum())
            fraud_approved_missed = int(((fraud_mask) & (actions == Action.APPROVE.value)).sum())
            
            fraud_intercepted_count = fraud_blocked + fraud_reviewed
            fraud_caught_pct = (fraud_intercepted_count / total_fraud_count * 100) if total_fraud_count > 0 else 0.0
            
            dollars_intercepted = float(np.sum(amounts[fraud_mask & (actions != Action.APPROVE.value)]))
            fraud_dollars_caught_pct = (dollars_intercepted / total_fraud_dollars * 100) if total_fraud_dollars > 0 else 0.0
            
            # False alarms (Legitimate transactions blocked or reviewed)
            legit_mask = (y_true == 0)
            legit_blocked = int((legit_mask & (actions == Action.BLOCK.value)).sum())
            legit_reviewed = int((legit_mask & (actions == Action.REVIEW.value)).sum())
            total_legit_impacted = legit_blocked + legit_reviewed
            
            total_modeled_cost = sum(expected_losses)
            
            results.append({
                "Risk_Posture": profile_name.value,
                "Review_Threshold": profile.operational_threshold_review,
                "Block_Threshold": profile.operational_threshold_block,
                "Pct_Approved": round(pct_approve, 4),
                "Pct_Reviewed": round(pct_review, 4),
                "Pct_Blocked": round(pct_block, 4),
                "Fraud_Intercepted_Pct": round(fraud_caught_pct, 2),
                "Fraud_Dollars_Intercepted_Pct": round(fraud_dollars_caught_pct, 2),
                "Fraud_Blocked_Count": fraud_blocked,
                "Fraud_Reviewed_Count": fraud_reviewed,
                "Fraud_Missed_Count": fraud_approved_missed,
                "Legit_Transactions_Blocked": legit_blocked,
                "Legit_Transactions_Reviewed": legit_reviewed,
                "Total_Legitimate_Impacted": total_legit_impacted,
                "Total_Expected_Modeled_Cost": round(total_modeled_cost, 2)
            })
            
        return pd.DataFrame(results)
