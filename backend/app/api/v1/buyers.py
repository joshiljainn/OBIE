"""
Buyers API Endpoints

CRUD operations for buyer entities.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.api import BuyerCreate, BuyerResponse, BuyerUpdate

router = APIRouter()


@router.get("")
async def list_buyers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    country: Optional[str] = None,
    industry: Optional[str] = None,
    verified_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """List buyers with filtering and pagination."""
    from sqlalchemy import select, func
    from app.models.buyer import BuyerEntity
    
    query = select(BuyerEntity).where(BuyerEntity.is_deleted == False)
    
    if country:
        query = query.where(BuyerEntity.country == country)
    if industry:
        query = query.where(BuyerEntity.industry.ilike(f"%{industry}%"))
    if verified_only:
        query = query.where(BuyerEntity.verification_status == "verified")
    
    query = query.order_by(BuyerEntity.reliability_score.desc(), BuyerEntity.legal_name)
    
    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    buyers = [BuyerResponse.model_validate(item) for item in items]
    
    return {
        "items": buyers,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{buyer_id}", response_model=BuyerResponse)
async def get_buyer(buyer_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific buyer by ID."""
    from sqlalchemy import select
    from app.models.buyer import BuyerEntity
    
    query = select(BuyerEntity).where(
        BuyerEntity.id == buyer_id,
        BuyerEntity.is_deleted == False,
    )
    
    result = await db.execute(query)
    buyer = result.scalar_one_or_none()
    
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer not found")
    
    return buyer


@router.post("", response_model=BuyerResponse)
async def create_buyer(buyer_data: BuyerCreate, db: AsyncSession = Depends(get_db)):
    """Create a new buyer entity."""
    from sqlalchemy import select
    from app.models.buyer import BuyerEntity
    
    # Check for duplicate by domain
    if buyer_data.domain:
        duplicate_query = select(BuyerEntity).where(
            BuyerEntity.domain == buyer_data.domain,
            BuyerEntity.is_deleted == False,
        )
        result = await db.execute(duplicate_query)
        existing = result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Buyer with this domain already exists",
            )
    
    buyer = BuyerEntity(**buyer_data.model_dump())
    db.add(buyer)
    await db.commit()
    await db.refresh(buyer)
    
    return buyer


@router.patch("/{buyer_id}", response_model=BuyerResponse)
async def update_buyer(
    buyer_id: int,
    buyer_data: BuyerUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a buyer entity."""
    from sqlalchemy import select
    from app.models.buyer import BuyerEntity
    
    query = select(BuyerEntity).where(
        BuyerEntity.id == buyer_id,
        BuyerEntity.is_deleted == False,
    )
    
    result = await db.execute(query)
    buyer = result.scalar_one_or_none()
    
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer not found")
    
    update_data = buyer_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(buyer, field, value)
    
    db.add(buyer)
    await db.commit()
    await db.refresh(buyer)
    
    return buyer


@router.delete("/{buyer_id}")
async def delete_buyer(buyer_id: int, db: AsyncSession = Depends(get_db)):
    """Soft delete a buyer entity."""
    from sqlalchemy import select
    from app.models.buyer import BuyerEntity
    
    query = select(BuyerEntity).where(
        BuyerEntity.id == buyer_id,
        BuyerEntity.is_deleted == False,
    )
    
    result = await db.execute(query)
    buyer = result.scalar_one_or_none()
    
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer not found")
    
    buyer.mark_as_deleted()
    db.add(buyer)
    await db.commit()
    
    return {"message": "Buyer deleted successfully"}
