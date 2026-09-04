"""Routes package."""

from app.api.routes.health import router as health_router
from app.api.routes.risk import router as risk_router
from app.api.routes.razorpay import router as razorpay_router
from app.api.routes.webhooks import router as webhooks_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.transactions import router as transactions_router
from app.api.routes.review import router as review_router
from app.api.routes.model import router as model_router
from app.api.routes.audit import router as audit_router
from app.api.routes.system import router as system_router

__all__ = [
    "health_router",
    "risk_router",
    "razorpay_router",
    "webhooks_router",
    "analytics_router",
    "transactions_router",
    "review_router",
    "model_router",
    "audit_router",
    "system_router"
]

