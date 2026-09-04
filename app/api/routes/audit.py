"""Audit trail logs route."""

from typing import Optional
from fastapi import APIRouter, Query, Depends
from app.config import get_settings
from app.storage.audit_store import AuditStore
from app.schemas.dashboard import AuditLogsResponse

router = APIRouter(prefix="/api/v1/audit", tags=["Audit Log"])


def get_audit_store() -> AuditStore:
    """Dependency injector for AuditStore."""
    settings = get_settings()
    return AuditStore(settings.SQLITE_DB_PATH)


@router.get("/logs", response_model=AuditLogsResponse, summary="Get Audit Logs")
async def get_audit_logs(
    limit: int = Query(50, ge=1, le=100, description="Max logs to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    action: Optional[str] = Query(None, description="Filter by action: APPROVE, REVIEW, BLOCK"),
    transaction_id: Optional[str] = Query(None, description="Filter by transaction reference"),
    store: AuditStore = Depends(get_audit_store)
) -> AuditLogsResponse:
    """
    Retrieve paginated immutable audit records.
    Never exposes internal secrets or credentials.
    """
    res = store.get_audit_logs(
        limit=limit,
        offset=offset,
        event_type=event_type,
        action=action,
        transaction_id=transaction_id
    )
    return AuditLogsResponse(**res)
