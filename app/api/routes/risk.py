"""Risk scoring route executing ML inference and deterministic policy decisioning."""

from fastapi import APIRouter, HTTPException, Depends
from app.schemas.risk import RiskScoreRequest, RiskScoreResponse
from app.services.risk_service import RiskService

router = APIRouter(prefix="/api/v1/risk", tags=["Risk Scoring"])


def get_risk_service() -> RiskService:
    """Dependency injector for RiskService."""
    return RiskService()


@router.post("/score", response_model=RiskScoreResponse, summary="Score Transaction Risk")
async def score_transaction(
    request: RiskScoreRequest,
    service: RiskService = Depends(get_risk_service)
) -> RiskScoreResponse:
    """
    Score a transaction using the production ML model and evaluate deterministic policy rules.
    """
    try:
        return service.score_transaction(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Risk evaluation error: {str(e)}")
