"""Transactions monitoring and analysis routes."""

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends, Body
from app.config import get_settings
from app.storage.audit_store import AuditStore
from app.schemas.dashboard import TransactionListResponse, TransactionDetailResponse

router = APIRouter(prefix="/api/v1/transactions", tags=["Transactions"])


def get_audit_store() -> AuditStore:
    """Dependency injector for AuditStore."""
    settings = get_settings()
    return AuditStore(settings.SQLITE_DB_PATH)


@router.get("", response_model=TransactionListResponse, summary="List Transactions")
async def list_transactions(
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    status: Optional[str] = Query(None, description="Filter by status: APPROVE, REVIEW, or BLOCK"),
    search: Optional[str] = Query(None, description="Search term for transaction/decision ID"),
    sort_by: str = Query("timestamp", description="Sort field: timestamp, risk_score, expected_loss"),
    order: str = Query("desc", description="Sort direction: asc or desc"),
    include_archived: bool = Query(False, description="Include archived transactions"),
    store: AuditStore = Depends(get_audit_store)
) -> TransactionListResponse:
    """
    Retrieve paginated, filterable transactions from the persistent AuditStore.
    Only exposes real stored records.
    """
    res = store.get_transactions(
        limit=limit,
        offset=offset,
        status=status,
        search=search,
        sort_by=sort_by,
        order=order,
        include_archived=include_archived
    )
    return TransactionListResponse(**res)


@router.get("/{transaction_id}", response_model=TransactionDetailResponse, summary="Get Transaction Detail")
async def get_transaction_detail(
    transaction_id: str,
    store: AuditStore = Depends(get_audit_store)
) -> TransactionDetailResponse:
    """
    Retrieve deep-dive risk evaluation details, deterministic rule triggers,
    historical audit trail, and correlated webhook metadata for a specific transaction.
    Returns 404 if not found.
    """
    data = store.get_transaction_detail(transaction_id)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction '{transaction_id}' not found."
        )
    return TransactionDetailResponse(**data)


@router.post("/{transaction_id}/archive", summary="Archive Transaction")
async def archive_transaction(
    transaction_id: str,
    payload: Dict[str, Any] = Body(default={}),
    store: AuditStore = Depends(get_audit_store)
):
    """
    Archive transaction from active views while appending an immutable TRANSACTION_ARCHIVED audit row.
    """
    try:
        res = store.archive_transaction(
            transaction_id=transaction_id,
            notes=payload.get("notes"),
            reason=payload.get("reason")
        )
        return {"success": True, "message": f"Transaction '{transaction_id}' archived.", **res}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Transaction '{transaction_id}' not found.")


@router.post("/{transaction_id}/rereview", summary="Re-review Transaction")
async def rereview_transaction(
    transaction_id: str,
    payload: Dict[str, Any] = Body(default={}),
    store: AuditStore = Depends(get_audit_store)
):
    """
    Re-open a transaction for manual review, appending a REVIEW_STARTED event to the audit trail.
    """
    try:
        res = store.rereview_transaction(
            transaction_id=transaction_id,
            notes=payload.get("notes"),
            reason=payload.get("reason")
        )
        return {"success": True, "message": f"Transaction '{transaction_id}' queued for re-review.", **res}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Transaction '{transaction_id}' not found.")
