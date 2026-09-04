"""Manual review queue and analyst decision routes."""

from fastapi import APIRouter, HTTPException, Query, Depends
from app.config import get_settings
from app.storage.audit_store import AuditStore
from app.schemas.dashboard import (
    ReviewQueueResponse,
    EvaluationQueueResponse,
    ReviewActionRequest,
    ReviewActionResponse
)

router = APIRouter(prefix="/api/v1/review", tags=["Review Queue"])


def get_audit_store() -> AuditStore:
    """Dependency injector for AuditStore."""
    settings = get_settings()
    return AuditStore(settings.SQLITE_DB_PATH)


@router.get("/queue", response_model=ReviewQueueResponse, summary="Get Pending Review Queue")
async def get_review_queue(
    limit: int = Query(50, ge=1, le=100, description="Max queue items to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    store: AuditStore = Depends(get_audit_store)
) -> ReviewQueueResponse:
    """
    Retrieve only live transactions whose actual current stored decision is REVIEW.
    """
    res = store.get_review_queue(limit=limit, offset=offset)
    return ReviewQueueResponse(**res)


@router.get("/evaluation-queue", response_model=EvaluationQueueResponse, summary="Get Model Evaluation Queue")
async def get_evaluation_queue(
    store: AuditStore = Depends(get_audit_store)
) -> EvaluationQueueResponse:
    """
    Retrieve the 3 genuine offline evaluation cases (MEDIUM, HIGH, CRITICAL)
    evaluated by the native ML model and decision engine on held-out IEEE-CIS data.
    """
    res = store.get_evaluation_queue()
    return EvaluationQueueResponse(**res)


@router.post("/{transaction_id}/action", response_model=ReviewActionResponse, summary="Submit Manual Review Action")
@router.post("/queue/{transaction_id}/action", response_model=ReviewActionResponse, include_in_schema=False)
async def submit_review_action(
    transaction_id: str,
    request: ReviewActionRequest,
    store: AuditStore = Depends(get_audit_store)
) -> ReviewActionResponse:
    """
    Execute safe, auditable manual review action ('APPROVE' or 'BLOCK').
    Preserves the original automated decision and creates an immutable audit record.
    """
    try:
        res = store.record_manual_review_action(
            transaction_id=transaction_id,
            action=request.action,
            notes=request.notes,
            reason=request.reason
        )
        return ReviewActionResponse(
            success=True,
            message=f"Transaction '{res['transaction_id']}' updated to '{res['new_action']}'.",
            transaction_id=res["transaction_id"],
            decision_id=res.get("decision_id"),
            previous_action=res["previous_action"],
            new_action=res["new_action"],
            audit_id=res["audit_id"],
            timestamp=res["timestamp"],
            notes=res.get("notes"),
            reason=res.get("reason")
        )
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction '{transaction_id}' not found in audit store."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record manual review action: {str(e)}")
