"""
Leads API Endpoints

CRUD operations for opportunities/leads.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.opportunity import Opportunity, OpportunityStatus
from app.schemas.api import (
    OpportunityCreate,
    OpportunityResponse,
    OpportunityUpdate,
    PaginatedResponse,
)

router = APIRouter()


@router.get("")
async def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[OpportunityStatus] = None,
    tier: Optional[str] = None,
    source: Optional[str] = None,
    product: Optional[str] = None,
    country: Optional[str] = None,
    min_score: Optional[float] = None,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    """
    List leads with filtering and pagination.
    
    - **page**: Page number (1-indexed)
    - **page_size**: Items per page (max 100)
    - **status**: Filter by status
    - **tier**: Filter by intent tier (S, A, B, C)
    - **source**: Filter by source name
    - **product**: Filter by product keyword
    - **country**: Filter by destination country
    - **min_score**: Minimum intent score
    """
    from sqlalchemy import select, func
    
    # Build query
    query = select(Opportunity).where(Opportunity.is_deleted == False)
    
    # Apply filters
    if status:
        query = query.where(Opportunity.status == status)
    if tier:
        query = query.where(Opportunity.intent_tier == tier.upper())
    if source:
        query = query.where(Opportunity.source_name == source)
    if product:
        query = query.where(Opportunity.product_normalized.ilike(f"%{product}%"))
    if country:
        query = query.where(Opportunity.destination_country == country)
    if min_score:
        query = query.where(Opportunity.intent_score >= min_score)
    
    # Order by score (highest first), then created_at
    query = query.order_by(Opportunity.intent_score.desc(), Opportunity.created_at.desc())
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    # Execute
    result = await db.execute(query)
    items = result.scalars().all()
    
    # Convert to response
    leads = [OpportunityResponse.model_validate(item) for item in items]
    
    return PaginatedResponse(
        items=leads,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{lead_id}", response_model=OpportunityResponse)
async def get_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific lead by ID.
    """
    from sqlalchemy import select
    
    query = select(Opportunity).where(
        Opportunity.id == lead_id,
        Opportunity.is_deleted == False,
    )
    
    result = await db.execute(query)
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    return lead


@router.post("", response_model=OpportunityResponse)
async def create_lead(
    lead_data: OpportunityCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new lead.
    
    This is typically used for manual imports or webhook integrations.
    """
    from sqlalchemy import select
    
    # Check for duplicates (by source_url)
    if lead_data.source_url:
        duplicate_query = select(Opportunity).where(
            Opportunity.source_url == lead_data.source_url,
            Opportunity.is_deleted == False,
        )
        result = await db.execute(duplicate_query)
        existing = result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Lead with this source URL already exists",
            )
    
    # Create new lead
    lead = Opportunity(**lead_data.model_dump())
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    
    return lead


@router.patch("/{lead_id}", response_model=OpportunityResponse)
async def update_lead(
    lead_id: int,
    lead_data: OpportunityUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update a lead.
    
    Used for status changes, notes, assignments, etc.
    """
    from sqlalchemy import select
    
    query = select(Opportunity).where(
        Opportunity.id == lead_id,
        Opportunity.is_deleted == False,
    )
    
    result = await db.execute(query)
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Update fields
    update_data = lead_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lead, field, value)
    
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    
    return lead


@router.delete("/{lead_id}")
async def delete_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Soft delete a lead.
    """
    from sqlalchemy import select
    
    query = select(Opportunity).where(
        Opportunity.id == lead_id,
        Opportunity.is_deleted == False,
    )
    
    result = await db.execute(query)
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Soft delete
    lead.mark_as_deleted()
    db.add(lead)
    await db.commit()
    
    return {"message": "Lead deleted successfully"}


@router.post("/{lead_id}/status")
async def update_lead_status(
    lead_id: int,
    status: OpportunityStatus,
    db: AsyncSession = Depends(get_db),
):
    """
    Update lead status (quick endpoint for workflow).
    """
    from sqlalchemy import select
    
    query = select(Opportunity).where(
        Opportunity.id == lead_id,
        Opportunity.is_deleted == False,
    )
    
    result = await db.execute(query)
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    lead.status = status
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    
    return {"message": f"Status updated to {status.value}"}
