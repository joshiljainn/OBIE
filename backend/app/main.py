"""
FastAPI Application

Main application entry point with middleware, routers, and lifecycle events.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_client import make_asgi_app

from app.config import settings
from app.database import check_db_health
from app.utils.logging import setup_logging
from app.utils.metrics import setup_metrics


# ─────────────────────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────────────────────

setup_logging()
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Lifecycle Events
# ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # ─────────────────────────────────────────────────────────
    # Startup
    # ─────────────────────────────────────────────────────────
    
    logger.info("Starting OBIE API...")
    
    # Health check database
    db_healthy = await check_db_health()
    if not db_healthy:
        logger.warning("Database connection unhealthy - will retry on request")
    
    # Setup metrics
    setup_metrics(app)
    
    logger.info(f"OBIE API v{settings.app_version} started in {settings.env} mode")
    
    yield
    
    # ─────────────────────────────────────────────────────────
    # Shutdown
    # ─────────────────────────────────────────────────────────
    
    logger.info("Shutting down OBIE API...")
    
    # Cleanup connections, close sessions, etc.
    
    logger.info("OBIE API shutdown complete")


# ─────────────────────────────────────────────────────────────
# Application Factory
# ─────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    """
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Export Buyer Intent Engine - Discover, score, and prioritize active import buyers",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    
    # ─────────────────────────────────────────────────────────
    # Middleware
    # ─────────────────────────────────────────────────────────
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods.split(","),
        allow_headers=settings.cors_allow_headers.split(","),
    )
    
    # Security headers (production)
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"],  # Configure appropriately
        )
    
    # ─────────────────────────────────────────────────────────
    # Metrics Endpoint (Prometheus)
    # ─────────────────────────────────────────────────────────
    
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
    
    # ─────────────────────────────────────────────────────────
    # Include Routers
    # ─────────────────────────────────────────────────────────
    
    from app.api.v1 import api_router
    
    app.include_router(api_router, prefix="/api/v1")
    
    # ─────────────────────────────────────────────────────────
    # Health Check Endpoint
    # ─────────────────────────────────────────────────────────
    
    @app.get("/health", tags=["Health"])
    async def health_check():
        """
        Health check endpoint for load balancers and monitoring.
        """
        db_healthy = await check_db_health()
        
        return {
            "status": "healthy" if db_healthy else "degraded",
            "database": "healthy" if db_healthy else "unhealthy",
            "version": settings.app_version,
            "env": settings.env,
        }
    
    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint with API information."""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/health",
            "metrics": "/metrics",
        }
    
    return app


# ─────────────────────────────────────────────────────────────
# Application Instance
# ─────────────────────────────────────────────────────────────

app = create_app()
