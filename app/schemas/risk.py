"""Pydantic schemas for internal risk scoring."""

from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field, field_validator
import math
from razorrisk.engine.types import CostProfileName, RiskTier, ConfidenceTier, Action


class RiskScoreRequest(BaseModel):
    """Structured input payload containing ULB benchmark feature schema."""
    
    transaction_id: str = Field(..., description="Unique transaction reference identifier")
    Time: float = Field(..., ge=0.0, description="Elapsed seconds since first benchmark transaction")
    Amount: float = Field(..., ge=0.0, description="Monetary transaction amount")
    
    # V1 through V28 numerical PCA features
    V1: float
    V2: float
    V3: float
    V4: float
    V5: float
    V6: float
    V7: float
    V8: float
    V9: float
    V10: float
    V11: float
    V12: float
    V13: float
    V14: float
    V15: float
    V16: float
    V17: float
    V18: float
    V19: float
    V20: float
    V21: float
    V22: float
    V23: float
    V24: float
    V25: float
    V26: float
    V27: float
    V28: float
    
    cost_profile: CostProfileName = Field(
        default=CostProfileName.BALANCED,
        description="Merchant business risk posture"
    )

    @field_validator("Time", "Amount", "V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10",
                     "V11", "V12", "V13", "V14", "V15", "V16", "V17", "V18", "V19", "V20",
                     "V21", "V22", "V23", "V24", "V25", "V26", "V27", "V28")
    @classmethod
    def validate_finite_floats(cls, v: float, info) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError(f"Feature '{info.field_name}' must be a finite numerical float")
        return v


class RiskScoreResponse(BaseModel):
    """Structured response from the deterministic Risk Decision Engine."""
    
    transaction_id: str
    decision_id: str
    fraud_probability: float
    calibrated_probability: Optional[float] = None
    uncertainty: float
    risk_score: float
    risk_tier: str
    confidence_tier: str
    recommended_action: str
    cost_profile: str
    triggered_rules: List[Dict[str, Any]]
    estimated_expected_loss: float
    explanation_factors: List[Dict[str, Any]]
    requires_human_review: bool
    model_version: str
    policy_version: str
    decision_timestamp: str
