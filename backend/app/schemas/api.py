"""
Pydantic Schemas for API Request/Validation

These schemas define the contract for API endpoints.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


# ─────────────────────────────────────────────────────────────
# Shared Schemas
# ─────────────────────────────────────────────────────────────

class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


# ─────────────────────────────────────────────────────────────
# Buyer Schemas
# ─────────────────────────────────────────────────────────────

class BuyerBase(BaseSchema):
    """Base buyer schema."""
    
    legal_name: str = Field(..., min_length=1, max_length=500)
    website: Optional[str] = None
    domain: Optional[str] = None
    country: Optional[str] = None
    country_name: Optional[str] = None
    city: Optional[str] = None
    industry: Optional[str] = None


class BuyerCreate(BuyerBase):
    """Schema for creating a buyer."""
    
    pass


class BuyerUpdate(BaseSchema):
    """Schema for updating a buyer (all fields optional)."""
    
    legal_name: Optional[str] = None
    aliases: Optional[str] = None
    website: Optional[str] = None
    domain: Optional[str] = None
    country: Optional[str] = None
    country_name: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    industry: Optional[str] = None
    industry_codes: Optional[str] = None
    company_type: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    reliability_score: Optional[float] = None
    verification_status: Optional[str] = None


class BuyerResponse(BuyerBase):
    """Schema for buyer responses."""
    
    id: int
    aliases: Optional[str] = None
    address: Optional[str] = None
    industry_codes: Optional[str] = None
    company_type: Optional[str] = None
    company_size: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    reliability_score: Optional[float] = None
    verification_status: str
    source_count: int
    first_seen_at: datetime
    last_active_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    is_deleted: bool


# ─────────────────────────────────────────────────────────────
# Opportunity Schemas
# ─────────────────────────────────────────────────────────────

class OpportunityBase(BaseSchema):
    """Base opportunity schema."""
    
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    buyer_name_raw: str = Field(..., min_length=1, max_length=500)
    buyer_type: Optional[str] = None
    product_text: str
    product_normalized: Optional[str] = None
    destination_country: Optional[str] = None


class OpportunityCreate(OpportunityBase):
    """Schema for creating an opportunity."""
    
    source_name: str
    source_url: str
    source_reference_id: Optional[str] = None
    quantity_text: Optional[str] = None
    budget_text: Optional[str] = None
    deadline: Optional[datetime] = None
    published_at: Optional[datetime] = None
    raw_payload: Optional[str] = None


class OpportunityUpdate(BaseSchema):
    """Schema for updating an opportunity."""
    
    title: Optional[str] = None
    description: Optional[str] = None
    buyer_type: Optional[str] = None
    product_normalized: Optional[str] = None
    hs_codes: Optional[str] = None
    quantity_value: Optional[float] = None
    quantity_unit: Optional[str] = None
    budget_value: Optional[float] = None
    budget_currency: Optional[str] = None
    incoterm: Optional[str] = None
    destination_city: Optional[str] = None
    deadline: Optional[datetime] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    notes: Optional[str] = None


class OpportunityScore(BaseSchema):
    """Schema for intent score."""
    
    score_total: float = Field(..., ge=0, le=100)
    tier: str  # S, A, B, C
    subscores: Dict[str, float]
    reason_codes: List[str]
    explain_text: str


class OpportunityResponse(OpportunityBase):
    """Schema for opportunity responses."""
    
    id: int
    buyer_entity_id: Optional[int] = None
    buyer_name_raw: str
    buyer_type: Optional[str] = None
    product_normalized: Optional[str] = None
    hs_codes: Optional[str] = None
    quantity_text: Optional[str] = None
    quantity_value: Optional[float] = None
    quantity_unit: Optional[str] = None
    budget_text: Optional[str] = None
    budget_value: Optional[float] = None
    budget_currency: Optional[str] = None
    incoterm: Optional[str] = None
    destination_city: Optional[str] = None
    deadline: Optional[datetime] = None
    published_at: Optional[datetime] = None
    source_name: str
    source_url: str
    source_reference_id: Optional[str] = None
    intent_score: Optional[float] = None
    intent_tier: Optional[str] = None
    score_breakdown: Optional[str] = None
    status: str
    assigned_to: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
    
    # Computed fields
    days_until_deadline: Optional[int] = None
    is_urgent: bool = False


# ─────────────────────────────────────────────────────────────
# Contact Schemas
# ─────────────────────────────────────────────────────────────

class ContactBase(BaseSchema):
    """Base contact schema."""
    
    name: str = Field(..., min_length=1, max_length=255)
    role: Optional[str] = None
    department: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None


class ContactCreate(ContactBase):
    """Schema for creating a contact."""
    
    buyer_entity_id: Optional[int] = None
    source: Optional[str] = None


class ContactResponse(ContactBase):
    """Schema for contact responses."""
    
    id: int
    buyer_entity_id: Optional[int] = None
    department: Optional[str] = None
    email_verified: bool
    email_verification_status: Optional[str] = None
    email_verification_confidence: Optional[float] = None
    phone_verified: bool
    source: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    # Computed
    is_decision_maker: bool = False


# ─────────────────────────────────────────────────────────────
# Source Schemas
# ─────────────────────────────────────────────────────────────

class SourceBase(BaseSchema):
    """Base source schema."""
    
    name: str
    display_name: str
    source_type: str
    base_url: Optional[str] = None
    description: Optional[str] = None


class SourceResponse(SourceBase):
    """Schema for source responses."""
    
    id: int
    is_active: bool
    priority: int
    config: Optional[str] = None
    robots_respected: bool
    rate_limit_per_minute: Optional[int] = None
    total_leads_ingested: int
    total_valid_leads: int
    avg_intent_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    
    # Computed
    validation_rate: float = 0.0


class SourceHealthResponse(BaseSchema):
    """Schema for source health metrics."""
    
    id: int
    source_id: int
    run_at: datetime
    run_duration_seconds: Optional[float] = None
    status: str
    records_fetched: int
    records_parsed: int
    records_validated: int
    records_deduped: int
    parse_success_rate: Optional[float] = None
    validation_success_rate: Optional[float] = None
    error_count: int
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None


# ─────────────────────────────────────────────────────────────
# API Response Wrappers
# ─────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    """Standard paginated response wrapper."""
    
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


class APIResponse(BaseModel):
    """Standard API response wrapper."""
    
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None
    errors: Optional[List[str]] = None


# ─────────────────────────────────────────────────────────────
# Lead Import/Export Schemas
# ─────────────────────────────────────────────────────────────

class LeadExportRow(BaseSchema):
    """Schema for CSV export row."""
    
    opportunity_id: int
    title: str
    buyer_name: str
    buyer_type: Optional[str] = None
    product: str
    quantity: Optional[str] = None
    budget: Optional[str] = None
    deadline: Optional[str] = None
    destination_country: Optional[str] = None
    intent_score: Optional[float] = None
    intent_tier: Optional[str] = None
    status: str
    source_name: str
    source_url: str
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_role: Optional[str] = None
    created_at: datetime


class LeadImportRow(BaseSchema):
    """Schema for CSV import row (external data)."""
    
    buyer_name: str
    product: str
    quantity: Optional[str] = None
    destination: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    source_url: Optional[str] = None
    notes: Optional[str] = None
