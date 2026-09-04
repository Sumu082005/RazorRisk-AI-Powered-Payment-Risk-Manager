"""Main FastAPI Application Entrypoint for RazorRisk."""

from contextlib import asynccontextmanager
import logging
import time
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles


from app.config import get_settings
from app.api.routes import (
    health_router,
    risk_router,
    razorpay_router,
    webhooks_router,
    analytics_router,
    transactions_router,
    review_router,
    model_router,
    audit_router,
    system_router
)
from app.storage.audit_store import AuditStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("razorrisk.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle manager."""
    settings = get_settings()
    app.state.start_time = time.time()
    logger.info(f"Starting RazorRisk API [Environment: {settings.RAZORRISK_ENV}]")
    
    # Initialize SQLite audit database schema
    audit_store = AuditStore(settings.SQLITE_DB_PATH)
    logger.info(f"Audit Store initialized at {settings.SQLITE_DB_PATH}")
    
    yield
    
    logger.info("Shutting down RazorRisk API.")


def create_app() -> FastAPI:
    """Application factory for RazorRisk FastAPI backend."""
    settings = get_settings()
    
    app = FastAPI(
        title="RazorRisk API",
        version="1.0.0",
        description="AI Risk Manager for Payment Fraud Detection (Razorpay AI Buildathon 2026)",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan
    )
    
    # CORS Configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register API Routers
    app.include_router(health_router)
    app.include_router(risk_router)
    app.include_router(razorpay_router)
    app.include_router(webhooks_router)
    app.include_router(analytics_router)
    app.include_router(transactions_router)
    app.include_router(review_router)
    app.include_router(model_router)
    app.include_router(audit_router)
    app.include_router(system_router)

    
    # Static Files and Dashboard Routing
    static_dir = Path(__file__).parent / "static"
    dashboard_file = static_dir / "dashboard" / "index.html"
    test_checkout_file = static_dir / "test_checkout.html"

    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", response_class=FileResponse, tags=["Dashboard"])
    @app.get("/dashboard", response_class=FileResponse, tags=["Dashboard"])
    async def get_dashboard():
        """Serve unified RazorRisk Fintech Dashboard SPA."""
        return FileResponse(dashboard_file, media_type="text/html")

    @app.get("/test-checkout", response_class=FileResponse, tags=["Test Utilities"])
    async def get_test_checkout():
        """Serve Razorpay Test Mode checkout page."""
        return FileResponse(test_checkout_file, media_type="text/html")

    return app



app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True
    )
