"""
Buyer Entity Model

Represents a unique buyer organization (company, government entity, NGO, etc.).
This is the canonical entity after deduplication across multiple sources.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class BuyerEntity(BaseModel):
    """
    Canonical buyer entity after entity resolution.
    
    This represents a unique organization that may appear across
    multiple sources with different names/aliases.
    
    Example:
        - Source A: "ABC Trading LLC"
        - Source B: "ABC Trading"
        - Source C: "Al Bashir Company"
        → All resolved to single BuyerEntity
    """
    
    __tablename__ = "buyer_entities"
    
    # ─────────────────────────────────────────────────────────
    # Core Identity
    # ─────────────────────────────────────────────────────────
    
    legal_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
        comment="Official registered company name",
    )
    
    aliases: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON array of known aliases/DBA names",
    )
    
    website: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        index=True,
        comment="Primary website URL",
    )
    
    domain: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Extracted domain (e.g., example.com)",
    )
    
    # ─────────────────────────────────────────────────────────
    # Location
    # ─────────────────────────────────────────────────────────
    
    country: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="ISO 3166-1 alpha-2 country code",
    )
    
    country_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Full country name",
    )
    
    city: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="City/region",
    )
    
    address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Full physical address",
    )
    
    # ─────────────────────────────────────────────────────────
    # Business Classification
    # ─────────────────────────────────────────────────────────
    
    industry: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Primary industry (e.g., Construction, Textiles)",
    )
    
    industry_codes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON array of HS/SIC/NAICS codes",
    )
    
    company_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="e.g., Private Limited, LLC, Government, NGO",
    )
    
    company_size: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="e.g., 1-10, 11-50, 51-200, 200+",
    )
    
    # ─────────────────────────────────────────────────────────
    # Contact Information
    # ─────────────────────────────────────────────────────────
    
    phone: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Primary phone number",
    )
    
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="General contact email",
    )
    
    linkedin_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="LinkedIn company page URL",
    )
    
    # ─────────────────────────────────────────────────────────
    # Trust & Reliability Scores
    # ─────────────────────────────────────────────────────────
    
    reliability_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="0-100 score based on history, verification",
    )
    
    verification_status: Mapped[str] = mapped_column(
        String(50),
        default="unverified",
        comment="unverified, partial, verified",
    )
    
    # ─────────────────────────────────────────────────────────
    # Metadata
    # ─────────────────────────────────────────────────────────
    
    source_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="Number of sources this entity appears in",
    )
    
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="When this entity was first discovered",
    )
    
    last_active_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Most recent activity timestamp",
    )
    
    # ─────────────────────────────────────────────────────────
    # Relationships
    # ─────────────────────────────────────────────────────────
    
    opportunities: Mapped[List["Opportunity"]] = relationship(
        "Opportunity",
        back_populates="buyer_entity",
        lazy="select",
    )
    
    contacts: Mapped[List["Contact"]] = relationship(
        "Contact",
        back_populates="buyer_entity",
        lazy="select",
    )
    
    # ─────────────────────────────────────────────────────────
    # Methods
    # ─────────────────────────────────────────────────────────
    
    def add_alias(self, alias: str) -> None:
        """Add an alias to the entity."""
        import json
        
        aliases = json.loads(self.aliases or "[]")
        if alias not in aliases:
            aliases.append(alias)
            self.aliases = json.dumps(aliases)
    
    def increment_source_count(self) -> None:
        """Increment the source count when found in a new source."""
        self.source_count += 1
    
    @property
    def is_verified(self) -> bool:
        """Check if entity is verified."""
        return self.verification_status == "verified"
    
    @property
    def display_name(self) -> str:
        """Get display name (shortened if needed)."""
        if len(self.legal_name) > 100:
            return self.legal_name[:97] + "..."
        return self.legal_name


# Import for type hints (avoid circular imports)
if TYPE_CHECKING:
    from app.models.opportunity import Opportunity
    from app.models.contact import Contact
