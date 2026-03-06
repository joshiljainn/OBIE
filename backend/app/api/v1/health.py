"""
Health API Endpoints

System health and diagnostics.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


@router.get("/status")
async def get_system_status(db: AsyncSession = Depends(get_db)):
    """
    Get comprehensive system health status.
    """
    from app.config import settings
    from app.database import check_db_health
    
    db_healthy = await check_db_health()
    
    # Check Redis (Celery)
    redis_healthy = False
    try:
        from app.tasks.celery_app import celery_app
        inspect = celery_app.control.inspect()
        ping_response = inspect.ping()
        redis_healthy = ping_response is not None
    except Exception:
        pass
    
    # Overall status
    all_healthy = db_healthy and redis_healthy
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "components": {
            "database": {
                "status": "healthy" if db_healthy else "unhealthy",
            },
            "redis": {
                "status": "healthy" if redis_healthy else "unhealthy",
            },
            "celery": {
                "status": "healthy" if redis_healthy else "unhealthy",
            },
        },
        "version": settings.app_version,
        "env": settings.env,
    }


@router.get("/metrics")
async def get_system_metrics(db: AsyncSession = Depends(get_db)):
    """
    Get system metrics (for dashboards).
    """
    from sqlalchemy import select, func
    from app.models.opportunity import Opportunity, OpportunityStatus
    from app.models.source import Source, SourceHealth
    from app.models.buyer import BuyerEntity
    
    # Lead counts by status
    status_query = select(
        Opportunity.status,
        func.count(Opportunity.id)
    ).where(
        Opportunity.is_deleted == False,
    ).group_by(Opportunity.status)
    
    status_result = await db.execute(status_query)
    leads_by_status = {row[0].value: row[1] for row in status_result.all()}
    
    # Total buyers
    buyers_query = select(func.count(BuyerEntity.id)).where(
        BuyerEntity.is_deleted == False,
    )
    buyers_result = await db.execute(buyers_query)
    total_buyers = buyers_result.scalar()
    
    # Source health
    source_health_query = select(
        func.count(Source.id)
    ).where(
        Source.is_deleted == False,
        Source.is_active == True,
    )
    source_result = await db.execute(source_health_query)
    active_sources = source_result.scalar()
    
    return {
        "leads": {
            "total": sum(leads_by_status.values()),
            "by_status": leads_by_status,
            "new": leads_by_status.get("new", 0),
            "contacted": leads_by_status.get("contacted", 0),
            "converted": leads_by_status.get("converted", 0),
        },
        "buyers": {
            "total": total_buyers,
        },
        "sources": {
            "active": active_sources,
        },
    }
