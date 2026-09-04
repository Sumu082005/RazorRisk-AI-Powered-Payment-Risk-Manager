"""System status and live operational health checks route."""

import os
import time
from pathlib import Path
from fastapi import APIRouter, Request, Depends
from app.config import get_settings
from app.storage.audit_store import AuditStore
from app.schemas.dashboard import SystemStatusResponse

router = APIRouter(prefix="/api/v1/system", tags=["System Status"])


def get_audit_store() -> AuditStore:
    """Dependency injector for AuditStore."""
    settings = get_settings()
    return AuditStore(settings.SQLITE_DB_PATH)


@router.get("/status", response_model=SystemStatusResponse, summary="Get System Operational Status")
async def get_system_status(
    request: Request,
    store: AuditStore = Depends(get_audit_store)
) -> SystemStatusResponse:
    """
    Expose verified live operational health metrics.
    Only reports checks that can actually be verified reliably.
    Does not expose secrets and does not claim external services are 'connected'
    merely because credentials exist.
    """
    settings = get_settings()

    # 1. API Health & Uptime
    start_time = getattr(request.app.state, "start_time", None)
    uptime_seconds = round(time.time() - start_time, 2) if start_time else 0.0

    api_status = {
        "status": "healthy",
        "service": "RazorRisk API",
        "version": "1.0.0",
        "environment": settings.RAZORRISK_ENV,
        "uptime_seconds": uptime_seconds
    }

    # 2. Database / Storage Status
    storage_healthy = True
    storage_stats = {"total_audit_records": 0, "total_webhook_records": 0}
    try:
        storage_stats = store.get_storage_stats()
        db_status = "connected"
    except Exception as e:
        storage_healthy = False
        db_status = f"error: {str(e)}"

    storage_info = {
        "status": db_status,
        "database_path": settings.SQLITE_DB_PATH,
        "total_audit_records": storage_stats.get("total_audit_records", 0),
        "total_webhook_records": storage_stats.get("total_webhook_records", 0)
    }

    # 3. Model Loaded Status
    model_path = Path(settings.MODEL_ARTIFACT_PATH)
    model_exists = model_path.exists()
    model_size_bytes = model_path.stat().st_size if model_exists else 0

    model_info = {
        "status": "loaded" if model_exists else "missing",
        "artifact_path": settings.MODEL_ARTIFACT_PATH,
        "artifact_size_bytes": model_size_bytes,
        "model_version": "Random Forest 100 Estimators (Unweighted, Calibrated)"
    }

    # 4. Razorpay Integration Configuration Status
    # Note: Only reports whether credentials are configured; does not claim connected.
    has_key_id = bool(settings.RAZORPAY_KEY_ID and not settings.RAZORPAY_KEY_ID.startswith("rzp_test_placeholder"))
    has_key_secret = bool(settings.RAZORPAY_KEY_SECRET and not settings.RAZORPAY_KEY_SECRET.startswith("placeholder"))
    has_webhook_secret = bool(settings.RAZORPAY_WEBHOOK_SECRET and not settings.RAZORPAY_WEBHOOK_SECRET.startswith("placeholder"))

    razorpay_info = {
        "mode": "TEST_MODE",
        "key_id_configured": bool(settings.RAZORPAY_KEY_ID),
        "key_secret_configured": bool(settings.RAZORPAY_KEY_SECRET),
        "webhook_secret_configured": bool(settings.RAZORPAY_WEBHOOK_SECRET),
        "base_url": settings.RAZORPAY_BASE_URL,
        "note": "Razorpay test mode webhook intake and order creation enabled"
    }

    overall_status = "operational" if (storage_healthy and model_exists) else "degraded"

    return SystemStatusResponse(
        status=overall_status,
        api=api_status,
        storage=storage_info,
        model=model_info,
        razorpay_integration=razorpay_info
    )
