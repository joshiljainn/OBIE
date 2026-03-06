"""
API v1 Router

Aggregates all v1 API endpoints.
"""
from fastapi import APIRouter

from app.api.v1 import leads, buyers, sources, reports, health


# ─────────────────────────────────────────────────────────────
# Main API Router
# ─────────────────────────────────────────────────────────────

api_router = APIRouter()


# ─────────────────────────────────────────────────────────────
# Include Sub-routers
# ─────────────────────────────────────────────────────────────

api_router.include_router(leads.router, prefix="/leads", tags=["Leads"])
api_router.include_router(buyers.router, prefix="/buyers", tags=["Buyers"])
api_router.include_router(sources.router, prefix="/sources", tags=["Sources"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(health.router, prefix="/health", tags=["Health"])


# ─────────────────────────────────────────────────────────────
# Root API Info
# ─────────────────────────────────────────────────────────────

@api_router.get("/")
async def api_root():
    """API v1 root information."""
    return {
        "version": "v1",
        "endpoints": {
            "leads": "/api/v1/leads",
            "buyers": "/api/v1/buyers",
            "sources": "/api/v1/sources",
            "reports": "/api/v1/reports",
            "health": "/api/v1/health",
        },
    }
