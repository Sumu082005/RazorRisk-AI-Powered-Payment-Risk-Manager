"""Structured Types, Enums, and Data Contracts for the RazorRisk Decision Engine."""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Any
import datetime
import uuid


class RiskTier(str, Enum):
    """Hierarchical classification of predicted transaction risk."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConfidenceTier(str, Enum):
    """Reliability and epistemic certainty of the model decision."""
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    MEDIUM_CONFIDENCE = "MEDIUM_CONFIDENCE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


class Action(str, Enum):
    """Deterministic operational policy action."""
    APPROVE = "APPROVE"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"


class CostProfileName(str, Enum):
    """Merchant business risk posture."""
    FRAUD_PREVENTION = "FRAUD_PREVENTION"
    BALANCED = "BALANCED"
    CUSTOMER_EXPERIENCE = "CUSTOMER_EXPERIENCE"


@dataclass(frozen=True)
class CostProfile:
    """Asymmetric business cost assumptions for risk decisioning."""
    name: CostProfileName
    description: str
    operational_threshold_review: float
    operational_threshold_block: float
    review_cost: float
    chargeback_fee: float
    false_positive_friction_cost: float
    review_accuracy: float = 0.95


@dataclass
class ModelEvidence:
    """Structured evidence payload supplied by the ML inference layer."""
    transaction_id: str
    transaction_amount: float
    fraud_probability: float
    calibrated_probability: Optional[float] = None
    uncertainty: Optional[float] = None
    tree_dispersion_std: Optional[float] = None
    feature_contributions: Dict[str, float] = field(default_factory=dict)
    raw_features: Dict[str, float] = field(default_factory=dict)
    model_version: str = "RandomForest-v1.0.0"


@dataclass
class TriggeredRule:
    """Audit record of a policy or safety rule triggered during evaluation."""
    rule_id: str
    rule_name: str
    severity: str  # INFO, WARNING, CRITICAL
    description: str
    action_impact: Optional[Action] = None


@dataclass
class DecisionResult:
    """Comprehensive, deterministic decision output contract."""
    decision_id: str
    transaction_id: str
    risk_score: float
    risk_tier: RiskTier
    confidence_tier: ConfidenceTier
    recommended_action: Action
    policy_id: str
    policy_version: str
    cost_profile: CostProfileName
    triggered_rules: List[TriggeredRule]
    estimated_expected_loss: float
    explanation_factors: List[Dict[str, Any]]
    requires_human_review: bool
    decision_timestamp: str
    model_version: str
    audit_event: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert decision result to a JSON-serializable dictionary."""
        d = asdict(self)
        d["risk_tier"] = self.risk_tier.value
        d["confidence_tier"] = self.confidence_tier.value
        d["recommended_action"] = self.recommended_action.value
        d["cost_profile"] = self.cost_profile.value
        return d
