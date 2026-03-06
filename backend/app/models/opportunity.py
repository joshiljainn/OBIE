"""
Opportunity Model

Represents a specific buying opportunity/requirement from a buyer.
This is the core "lead" that gets scored and tracked.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

import enum

from app.models.base import BaseModel


class OpportunityStatus(enum.Enum):
    """Opportunity lifecycle status."""
    
    NEW = "new"
    REVIEWED = "reviewed"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"
    CONVERTED = "converted"
    ARCHIVED = "archived"


class Opportunity(BaseModel):
    """
    A specific buying opportunity from a buyer.
    
    This is created from ingested lead signals after normalization
    and entity resolution. Each opportunity is linked to a BuyerEntity.
    
    Example:
        Buyer: "ABC Trading LLC"
        Opportunity: "Need 500 tons of plywood CIF Dubai by March 2026"
    """
    
    __tablename__ = "opportunities"
    
    # ─────────────────────────────────────────────────────────
    # Core Identity
    # ─────────────────────────────────────────────────────────
    
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Opportunity title/summary",
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Full opportunity description",
    )
    
    # ─────────────────────────────────────────────────────────
    # Buyer Relationship
    # ─────────────────────────────────────────────────────────
    
    buyer_entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("buyer_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Resolved buyer entity (NULL if not yet resolved)",
    )
    
    buyer_name_raw: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Raw buyer name from source",
    )
    
    buyer_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="e.g., Importer, Distributor, Government, Retailer",
    )
    
    # ─────────────────────────────────────────────────────────
    # Product/Service Details
    # ─────────────────────────────────────────────────────────
    
    product_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Raw product description from source",
    )
    
    product_normalized: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Normalized product category",
    )
    
    hs_codes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON array of HS codes",
    )
    
    quantity_text: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Raw quantity text (e.g., '500 tons')",
    )
    
    quantity_value: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Parsed quantity value",
    )
    
    quantity_unit: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="e.g., tons, kg, pieces, containers",
    )
    
    # ─────────────────────────────────────────────────────────
    # Financial Details
    # ─────────────────────────────────────────────────────────
    
    budget_text: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Raw budget text",
    )
    
    budget_value: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Parsed budget amount",
    )
    
    budget_currency: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="ISO 4217 currency code",
    )
    
    incoterm: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="e.g., FOB, CIF, EXW, DDP",
    )
    
    # ─────────────────────────────────────────────────────────
    # Location & Timing
    # ─────────────────────────────────────────────────────────
    
    destination_country: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Destination country (ISO code)",
    )
    
    destination_city: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Destination city",
    )
    
    deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Submission/response deadline",
    )
    
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the opportunity was published",
    )
    
    # ─────────────────────────────────────────────────────────
    # Source Information
    # ─────────────────────────────────────────────────────────
    
    source_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Source adapter name (e.g., 'ted', 'tradekey')",
    )
    
    source_url: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
        comment="Direct URL to the opportunity",
    )
    
    source_reference_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Source's internal ID (for dedupe)",
    )
    
    raw_payload: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON of raw source data (for debugging)",
    )
    
    # ─────────────────────────────────────────────────────────
    # Intent Scoring
    # ─────────────────────────────────────────────────────────
    
    intent_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Calculated intent score (0-100)",
    )
    
    intent_tier: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        index=True,
        comment="S, A, B, or C tier",
    )
    
    score_breakdown: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON of subscores and reason codes",
    )
    
    # ─────────────────────────────────────────────────────────
    # Status & Workflow
    # ─────────────────────────────────────────────────────────
    
    status: Mapped[OpportunityStatus] = mapped_column(
        Enum(OpportunityStatus),
        default=OpportunityStatus.NEW,
        nullable=False,
        index=True,
    )
    
    assigned_to: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="User/team assigned to this opportunity",
    )
    
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Internal notes",
    )
    
    # ─────────────────────────────────────────────────────────
    # Relationships
    # ─────────────────────────────────────────────────────────
    
    buyer_entity: Mapped[Optional["BuyerEntity"]] = relationship(
        "BuyerEntity",
        back_populates="opportunities",
        lazy="joined",
    )
    
    contacts: Mapped[List["Contact"]] = relationship(
        "Contact",
        secondary="opportunity_contacts",
        lazy="select",
    )
    
    # ─────────────────────────────────────────────────────────
    # Methods
    # ─────────────────────────────────────────────────────────
    
    @property
    def is_urgent(self) -> bool:
        """Check if opportunity is urgent (deadline < 30 days)."""
        if not self.deadline:
            return False
        
        from datetime import timedelta
        days_left = (self.deadline - datetime.utcnow()).days
        return 0 < days_left <= 30
    
    @property
    def is_expired(self) -> bool:
        """Check if deadline has passed."""
        if not self.deadline:
            return False
        
        return self.deadline < datetime.utcnow()
    
    @property
    def days_until_deadline(self) -> Optional[int]:
        """Get days remaining until deadline."""
        if not self.deadline:
            return None
        
        from datetime import timedelta
        delta = self.deadline - datetime.utcnow()
        return delta.days
    
    def update_score(self, score: float, tier: str, breakdown: dict) -> None:
        """Update intent score with breakdown."""
        import json
        
        self.intent_score = score
        self.intent_tier = tier
        self.score_breakdown = json.dumps(breakdown)


# Import for type hints
if TYPE_CHECKING:
    from app.models.buyer import BuyerEntity
    from app.models.contact import Contact
