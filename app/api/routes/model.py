"""Model performance and verified offline benchmark metrics route."""

from typing import Dict, Any
from fastapi import APIRouter, Depends
from app.config import get_settings
from app.storage.audit_store import AuditStore
from app.schemas.dashboard import ModelMetricsResponse

router = APIRouter(prefix="/api/v1/model", tags=["Model Performance"])


def get_audit_store() -> AuditStore:
    """Dependency injector for AuditStore."""
    settings = get_settings()
    return AuditStore(settings.SQLITE_DB_PATH)


@router.get("/metrics", response_model=ModelMetricsResponse, summary="Get Model Benchmark Metrics")
async def get_model_metrics() -> ModelMetricsResponse:
    """
    Expose verified offline benchmark evaluation metrics for the production Random Forest model.
    Clearly labeled as offline benchmark metrics on the ULB dataset; does NOT imply live production metrics.
    """
    return ModelMetricsResponse(
        evaluation_type="OFFLINE BENCHMARK EVALUATION",
        dataset="ULB Credit Card Fraud Detection",
        pr_auc=0.7866,
        roc_auc=0.9595,
        precision=0.9342,
        recall=0.7474,
        f1=0.8304,
        operating_threshold=0.34,
        fraud_prevalence_pct=0.172749,
        confusion_matrix={
            "true_positives": 71,
            "false_positives": 5,
            "true_negatives": 56646,
            "false_negatives": 24
        },
        benchmark_scenarios=[
            {
                "scenario": "Balanced (Scenario B)",
                "threshold": 0.34,
                "precision": 0.9342,
                "recall": 0.7474,
                "f1": 0.8304,
                "description": "Optimized trade-off between fraud capture and user friction"
            },
            {
                "scenario": "High-Recall (Scenario A)",
                "threshold": 0.37,
                "precision": 0.9467,
                "recall": 0.7474,
                "f1": 0.8353,
                "description": "Maximal fraud capture with conservative exposure"
            },
            {
                "scenario": "High-Precision (Scenario C)",
                "threshold": 0.22,
                "precision": 0.9012,
                "recall": 0.7684,
                "f1": 0.8295,
                "description": "Minimal customer false positive friction"
            },
            {
                "scenario": "Default Benchmark",
                "threshold": 0.50,
                "precision": 0.9589,
                "recall": 0.7368,
                "f1": 0.8333,
                "description": "Standard uncalibrated 0.50 threshold"
            }
        ],
        disclaimer=(
            "Metrics reflect offline held-out test evaluation on the ULB Credit Card Fraud Detection benchmark dataset. "
            "They do NOT represent live Razorpay test or production environment metrics."
        )
    )


@router.get("/live-distribution", summary="Get Live Native AI Risk Distribution")
async def get_live_risk_distribution(store: AuditStore = Depends(get_audit_store)) -> Dict[str, Any]:
    """
    Return live risk distribution statistics across all NATIVE_AI_SCORED transactions.
    """
    return store.get_live_risk_distribution()


@router.get("/offline-coverage", summary="Get Offline Model Risk Coverage")
async def get_offline_risk_coverage(store: AuditStore = Depends(get_audit_store)) -> Dict[str, Any]:
    """
    Return offline held-out evaluation risk coverage metrics and representative tier examples (LOW, MEDIUM, HIGH, CRITICAL).
    """
    return store.get_offline_risk_coverage()

