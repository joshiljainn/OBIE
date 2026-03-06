"""
Reports API Endpoints

Export, analytics, and reporting.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


@router.get("/summary")
async def get_summary_report(
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """
    Get summary statistics for the last N days.
    """
    from sqlalchemy import select, func
    from app.models.opportunity import Opportunity
    from datetime import timedelta
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Total leads
    total_query = select(func.count(Opportunity.id)).where(
        Opportunity.created_at >= cutoff,
        Opportunity.is_deleted == False,
    )
    total_result = await db.execute(total_query)
    total_leads = total_result.scalar()
    
    # By tier
    tier_query = select(
        Opportunity.intent_tier,
        func.count(Opportunity.id)
    ).where(
        Opportunity.created_at >= cutoff,
        Opportunity.is_deleted == False,
    ).group_by(Opportunity.intent_tier)
    
    tier_result = await db.execute(tier_query)
    by_tier = {row[0]: row[1] for row in tier_result.all()}
    
    # By status
    status_query = select(
        Opportunity.status,
        func.count(Opportunity.id)
    ).where(
        Opportunity.created_at >= cutoff,
        Opportunity.is_deleted == False,
    ).group_by(Opportunity.status)
    
    status_result = await db.execute(status_query)
    by_status = {row[0].value: row[1] for row in status_result.all()}
    
    # By source
    source_query = select(
        Opportunity.source_name,
        func.count(Opportunity.id)
    ).where(
        Opportunity.created_at >= cutoff,
        Opportunity.is_deleted == False,
    ).group_by(Opportunity.source_name)
    
    source_result = await db.execute(source_query)
    by_source = {row[0]: row[1] for row in source_result.all()}
    
    # Average score
    avg_score_query = select(func.avg(Opportunity.intent_score)).where(
        Opportunity.created_at >= cutoff,
        Opportunity.is_deleted == False,
        Opportunity.intent_score.isnot(None),
    )
    avg_result = await db.execute(avg_score_query)
    avg_score = avg_result.scalar() or 0
    
    return {
        "period_days": days,
        "total_leads": total_leads,
        "by_tier": by_tier,
        "by_status": by_status,
        "by_source": by_source,
        "average_intent_score": round(avg_score, 2),
    }


@router.get("/export/csv")
async def export_leads_csv(
    status: Optional[str] = None,
    tier: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """
    Export leads to CSV format.
    """
    import csv
    import io
    from datetime import timedelta
    from fastapi.responses import StreamingResponse
    
    from app.models.opportunity import Opportunity
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Build query
    from sqlalchemy import select
    
    query = select(Opportunity).where(
        Opportunity.created_at >= cutoff,
        Opportunity.is_deleted == False,
    )
    
    if status:
        query = query.where(Opportunity.status == status)
    if tier:
        query = query.where(Opportunity.intent_tier == tier.upper())
    
    query = query.order_by(Opportunity.intent_score.desc())
    
    result = await db.execute(query)
    leads = result.scalars().all()
    
    # Create CSV
    output = io.StringIO()
    fieldnames = [
        "opportunity_id", "title", "buyer_name", "buyer_type",
        "product", "quantity", "budget", "deadline",
        "destination_country", "intent_score", "intent_tier",
        "status", "source_name", "source_url", "created_at"
    ]
    
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for lead in leads:
        writer.writerow({
            "opportunity_id": lead.id,
            "title": lead.title,
            "buyer_name": lead.buyer_name_raw,
            "buyer_type": lead.buyer_type,
            "product": lead.product_normalized or lead.product_text[:100],
            "quantity": lead.quantity_text,
            "budget": lead.budget_text,
            "deadline": lead.deadline.isoformat() if lead.deadline else None,
            "destination_country": lead.destination_country,
            "intent_score": lead.intent_score,
            "intent_tier": lead.intent_tier,
            "status": lead.status.value,
            "source_name": lead.source_name,
            "source_url": lead.source_url,
            "created_at": lead.created_at.isoformat(),
        })
    
    output.seek(0)
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"obie_leads_{timestamp}.csv"
    
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/top-buyers")
async def get_top_buyers(
    limit: int = Query(50, ge=1, le=200),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """
    Get top buyers by opportunity count and score in the last N days.
    """
    from datetime import timedelta
    from sqlalchemy import select, func
    from app.models.buyer import BuyerEntity
    from app.models.opportunity import Opportunity
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    query = (
        select(
            BuyerEntity,
            func.count(Opportunity.id).label("opportunity_count"),
            func.avg(Opportunity.intent_score).label("avg_score"),
        )
        .join(Opportunity, BuyerEntity.id == Opportunity.buyer_entity_id)
        .where(
            Opportunity.created_at >= cutoff,
            Opportunity.is_deleted == False,
            BuyerEntity.is_deleted == False,
        )
        .group_by(BuyerEntity.id)
        .order_by(func.count(Opportunity.id).desc(), func.avg(Opportunity.intent_score).desc())
        .limit(limit)
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    buyers = []
    for row in rows:
        buyer = row[0]
        buyers.append({
            "id": buyer.id,
            "name": buyer.legal_name,
            "country": buyer.country,
            "industry": buyer.industry,
            "opportunity_count": row.opportunity_count,
            "average_score": round(row.avg_score, 2) if row.avg_score else 0,
            "website": buyer.website,
        })
    
    return {"buyers": buyers, "period_days": days}


@router.get("/source-performance")
async def get_source_performance(
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """
    Get source performance metrics.
    """
    from datetime import timedelta
    from sqlalchemy import select, func, distinct
    from app.models.source import Source, SourceHealth, SourceHealthStatus
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Get health records
    query = (
        select(
            Source.name,
            Source.display_name,
            func.avg(SourceHealth.parse_success_rate).label("avg_parse_rate"),
            func.avg(SourceHealth.validation_success_rate).label("avg_validation_rate"),
            func.sum(SourceHealth.records_fetched).label("total_fetched"),
            func.sum(SourceHealth.records_validated).label("total_validated"),
            func.sum(
                func.case(
                    (SourceHealth.status == SourceHealthStatus.HEALTHY, 1),
                    else_=0,
                )
            ).label("healthy_runs"),
            func.count(SourceHealth.id).label("total_runs"),
        )
        .join(SourceHealth, Source.id == SourceHealth.source_id)
        .where(
            SourceHealth.run_at >= cutoff,
            Source.is_deleted == False,
        )
        .group_by(Source.id, Source.name, Source.display_name)
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    sources = []
    for row in rows:
        sources.append({
            "name": row.name,
            "display_name": row.display_name,
            "avg_parse_rate": round(row.avg_parse_rate, 2) if row.avg_parse_rate else 0,
            "avg_validation_rate": round(row.avg_validation_rate, 2) if row.avg_validation_rate else 0,
            "total_records_fetched": row.total_fetched or 0,
            "total_records_validated": row.total_validated or 0,
            "healthy_runs": row.healthy_runs,
            "total_runs": row.total_runs,
            "health_percentage": round((row.healthy_runs / row.total_runs * 100), 2) if row.total_runs > 0 else 0,
        })
    
    return {"sources": sources, "period_days": days}
