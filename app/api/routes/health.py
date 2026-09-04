"""Health check route."""

from fastapi import APIRouter
from app.config import get_settings

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Service Health Check")
async def health_check():
    """
    Public health check endpoint.
    Exposes no secrets, system paths, or sensitive credentials.
    """
    settings = get_settings()
    return {
        "status": "ok",
        "service": "RazorRisk API",
        "environment": settings.RAZORRISK_ENV
    }
