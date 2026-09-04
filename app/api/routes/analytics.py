"""Analytics and overview dashboard metrics route."""

from fastapi import APIRouter, Depends
from app.config import get_settings
from app.storage.audit_store import AuditStore
from app.schemas.dashboard import AnalyticsOverviewResponse

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics & Overview"])


def get_audit_store() -> AuditStore:
    """Dependency injector for AuditStore."""
    settings = get_settings()
    return AuditStore(settings.SQLITE_DB_PATH)


@router.get("/overview", response_model=AnalyticsOverviewResponse, summary="Get Risk Overview Aggregates")
async def get_risk_overview(
    store: AuditStore = Depends(get_audit_store)
) -> AnalyticsOverviewResponse:
    """
    Retrieve live aggregated metrics derived reliably from stored audit records.
    Returns transaction counts, decision distribution, risk tiers, and total amounts.
    Never fabricates historical data.
    """
    data = store.get_analytics_overview()
    return AnalyticsOverviewResponse(**data)
