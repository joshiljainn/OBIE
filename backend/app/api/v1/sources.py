"""
Sources API Endpoints

Source management and health monitoring.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.api import SourceHealthResponse, SourceResponse

router = APIRouter()


@router.get("", response_model=List[SourceResponse])
async def list_sources(
    active_only: bool = True,
    source_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all configured data sources."""
    from sqlalchemy import select
    from app.models.source import Source
    
    query = select(Source).where(Source.is_deleted == False)
    
    if active_only:
        query = query.where(Source.is_active == True)
    if source_type:
        query = query.where(Source.source_type == source_type)
    
    query = query.order_by(Source.priority.desc(), Source.name)
    
    result = await db.execute(query)
    sources = result.scalars().all()
    
    return [SourceResponse.model_validate(s) for s in sources]


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(source_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific source by ID."""
    from sqlalchemy import select
    from app.models.source import Source
    
    query = select(Source).where(
        Source.id == source_id,
        Source.is_deleted == False,
    )
    
    result = await db.execute(query)
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    return source


@router.get("/{source_id}/health", response_model=List[SourceHealthResponse])
async def get_source_health(
    source_id: int,
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get health history for a source (last N runs)."""
    from sqlalchemy import select
    from app.models.source import SourceHealth
    
    query = select(SourceHealth).where(
        SourceHealth.source_id == source_id,
    ).order_by(SourceHealth.run_at.desc()).limit(limit)
    
    result = await db.execute(query)
    health_records = result.scalars().all()
    
    return [SourceHealthResponse.model_validate(h) for h in health_records]


@router.post("/{source_id}/trigger")
async def trigger_source_ingestion(
    source_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger manual ingestion for a source.
    
    This queues a Celery task to run the ingestion.
    """
    from app.models.source import Source
    from app.tasks.ingestion_tasks import ingest_source
    
    # Verify source exists
    query = select(Source).where(
        Source.id == source_id,
        Source.is_deleted == False,
    )
    result = await db.execute(query)
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    if not source.is_active:
        raise HTTPException(status_code=400, detail="Source is not active")
    
    # Queue ingestion task
    task = ingest_source.delay(source.name)
    
    return {
        "message": f"Ingestion triggered for {source.name}",
        "task_id": task.id,
    }


@router.patch("/{source_id}/toggle")
async def toggle_source_status(source_id: int, db: AsyncSession = Depends(get_db)):
    """Toggle source active/inactive status."""
    from sqlalchemy import select
    from app.models.source import Source
    
    query = select(Source).where(
        Source.id == source_id,
        Source.is_deleted == False,
    )
    
    result = await db.execute(query)
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    source.is_active = not source.is_active
    db.add(source)
    await db.commit()
    await db.refresh(source)
    
    return {
        "message": f"Source {'activated' if source.is_active else 'deactivated'}",
        "is_active": source.is_active,
    }
