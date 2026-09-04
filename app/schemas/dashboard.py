"""Pydantic schemas for RazorRisk Dashboard and Monitoring APIs."""

from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field, field_validator


# =====================================================================
# 1. ANALYTICS / OVERVIEW SCHEMAS
# =====================================================================
class AnalyticsOverviewResponse(BaseModel):
    """Aggregated live metrics for Risk Overview screen."""
    transactions_monitored: int = Field(..., description="Total monitored transactions")
    approved: int = Field(..., description="Count of approved transactions")
    review: int = Field(..., description="Count of transactions in review state")
    blocked: int = Field(..., description="Count of blocked transactions")
    total_amount: float = Field(..., description="Aggregated monetary transaction amount")
    approval_rate_pct: float = Field(..., description="Percentage of monitored transactions approved")
    decision_distribution: Dict[str, int] = Field(..., description="Counts per decision action")
    risk_tier_distribution: Dict[str, int] = Field(..., description="Counts per risk tier")

    # Real Measured AI Pipeline Coverage Metrics
    ai_analyzed_count: int = Field(default=0, description="Count of transactions legitimately analyzed by Random Forest ML model")
    model_not_applicable_count: int = Field(default=0, description="Count of transactions outside model feature space safely escalated to human review")
    ai_escalated_count: int = Field(default=0, description="Count of transactions where AI model recommended review")
    ai_applicability_rate_pct: float = Field(default=0.0, description="Measured percentage of transactions evaluated by ML pipeline")
    manual_overrides_count: int = Field(default=0, description="Count of analyst review actions conducted")
    final_user_approvals: int = Field(default=0, description="Total transactions finalized as approved")
    final_user_blocks: int = Field(default=0, description="Total transactions finalized as blocked")



# =====================================================================
# 2. TRANSACTIONS LIST & DETAIL SCHEMAS
# =====================================================================
class TransactionSummaryItem(BaseModel):
    """Summary item for Transactions monitoring table."""
    audit_id: str
    transaction_id: str
    decision_id: Optional[str] = None
    event_type: str
    risk_score: Optional[float] = None
    risk_tier: Optional[str] = None
    confidence_tier: Optional[str] = None
    action: str
    cost_profile: str
    expected_loss: Optional[float] = None
    amount: Optional[float] = None
    currency: Optional[str] = "INR"
    timestamp: str
    ai_recommendation: Optional[str] = None
    human_decision: Optional[str] = None
    is_override: bool = False
    status_label: Optional[str] = None


class TransactionListResponse(BaseModel):
    """Paginated list of transactions."""
    total: int
    limit: int
    offset: int
    items: List[TransactionSummaryItem]


class TransactionDetailResponse(BaseModel):
    """Deep-dive transaction risk analysis details."""
    audit_id: str
    transaction_id: str
    decision_id: Optional[str] = None
    event_type: str
    risk_score: Optional[float] = None
    risk_tier: Optional[str] = None
    confidence_tier: Optional[str] = None
    action: str
    cost_profile: str
    expected_loss: Optional[float] = None
    amount: Optional[float] = None
    currency: Optional[str] = "INR"
    timestamp: str
    ai_recommendation: Optional[str] = None
    human_decision: Optional[str] = None
    is_override: bool = False
    status_label: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    triggered_rules: List[Dict[str, Any]] = []
    explanation_factors: List[Dict[str, Any]] = []
    history: List[Dict[str, Any]] = []
    correlated_webhook: Optional[Dict[str, Any]] = None


# =====================================================================
# 3. REVIEW QUEUE SCHEMAS
# =====================================================================
class ReviewQueueItem(BaseModel):
    """Transaction item awaiting human review."""
    audit_id: str
    transaction_id: str
    decision_id: Optional[str] = None
    event_type: str
    risk_score: Optional[float] = None
    risk_tier: Optional[str] = None
    confidence_tier: Optional[str] = None
    action: str
    cost_profile: str
    expected_loss: Optional[float] = None
    amount: Optional[float] = None
    currency: Optional[str] = "INR"
    triggered_rules: List[Dict[str, Any]] = []
    timestamp: str


class ReviewQueueResponse(BaseModel):
    """Paginated review queue response."""
    total: int
    limit: int
    offset: int
    items: List[ReviewQueueItem]


class EvaluationQueueItem(BaseModel):
    """Offline held-out evaluation case for risk workflow demonstration."""
    eval_id: str
    amount: Optional[float] = None
    currency: Optional[str] = "USD"
    risk_score: float
    risk_tier: str
    confidence_tier: str
    ai_recommendation: str
    source: str = "OFFLINE / HELD-OUT IEEE-CIS"
    is_offline_eval: bool = True
    status_label: str
    latest_action: str
    human_decision: Optional[str] = None
    is_override: bool = False
    timestamp: str
    extracted_features: Dict[str, Any] = {}


class EvaluationQueueResponse(BaseModel):
    """Model Evaluation Queue response containing genuine held-out evaluation cases."""
    items: List[EvaluationQueueItem]
    total: int
    disclaimer: str = (
        "These cases are automatically selected from held-out evaluation data "
        "using the same native ML model and decision engine. They are not live Razorpay transactions."
    )


class ReviewActionRequest(BaseModel):
    """Manual decision action on review queue transaction."""
    action: str = Field(..., description="Target decision: 'APPROVE', 'BLOCK', or 'REVIEW'")
    notes: Optional[str] = Field(None, max_length=1000, description="Reviewer justification or context notes")
    reason: Optional[str] = Field(None, max_length=500, description="Structured action reason code or category")

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        clean = v.upper().strip()
        if clean not in ("APPROVE", "BLOCK", "REVIEW"):
            raise ValueError("Manual review action must be 'APPROVE', 'BLOCK', or 'REVIEW'")
        return clean


class ReviewActionResponse(BaseModel):
    """Result of an immutable manual review audit log entry."""
    success: bool
    message: str
    transaction_id: str
    decision_id: Optional[str] = None
    previous_action: str
    new_action: str
    audit_id: str
    timestamp: str
    confidence_tier: Optional[str] = None
    notes: Optional[str] = None
    reason: Optional[str] = None


# =====================================================================
# 4. MODEL PERFORMANCE SCHEMAS
# =====================================================================
class ModelMetricsResponse(BaseModel):
    """Verified offline benchmark performance metrics."""
    evaluation_type: str = "OFFLINE BENCHMARK EVALUATION"
    dataset: str = "ULB Credit Card Fraud Detection"
    pr_auc: float = 0.7866
    roc_auc: float = 0.9595
    precision: float = 0.9342
    recall: float = 0.7474
    f1: float = 0.8304
    operating_threshold: float = 0.34
    fraud_prevalence_pct: float = 0.172749
    confusion_matrix: Dict[str, int]
    benchmark_scenarios: List[Dict[str, Any]]
    disclaimer: str = (
        "Metrics reflect offline held-out test evaluation on the ULB Credit Card Fraud Detection benchmark dataset. "
        "They do NOT represent live Razorpay test or production environment metrics."
    )


# =====================================================================
# 5. AUDIT LOG SCHEMAS
# =====================================================================
class AuditLogItem(BaseModel):

    """Structured audit trail item."""
    audit_id: str
    decision_id: Optional[str] = None
    transaction_id: str
    event_type: str
    risk_score: Optional[float] = None
    risk_tier: Optional[str] = None
    confidence_tier: Optional[str] = None
    action: str
    cost_profile: str
    expected_loss: Optional[float] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: str


class AuditLogsResponse(BaseModel):
    """Paginated audit logs response."""
    total: int
    limit: int
    offset: int
    items: List[AuditLogItem]


# =====================================================================
# 6. SYSTEM STATUS SCHEMAS
# =====================================================================
class SystemStatusResponse(BaseModel):
    """Verified live component health status."""
    status: str
    api: Dict[str, Any]
    storage: Dict[str, Any]
    model: Dict[str, Any]
    razorpay_integration: Dict[str, Any]
