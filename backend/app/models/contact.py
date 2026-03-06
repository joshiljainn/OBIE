"""
Contact Model

Represents individual contacts at buyer organizations.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


# ─────────────────────────────────────────────────────────────
# Association Table: Opportunity <-> Contact (Many-to-Many)
# ─────────────────────────────────────────────────────────────

opportunity_contacts = Table(
    "opportunity_contacts",
    BaseModel.metadata,
    Column("opportunity_id", ForeignKey("opportunities.id", ondelete="CASCADE"), primary_key=True),
    Column("contact_id", ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True),
    Column("is_primary", Boolean, default=False, comment="Primary contact for this opportunity"),
)


class Contact(BaseModel):
    """
    Individual contact person at a buyer organization.
    
    Contacts are extracted during enrichment and linked to
    both BuyerEntity and specific Opportunities.
    """
    
    __tablename__ = "contacts"
    
    # ─────────────────────────────────────────────────────────
    # Core Identity
    # ─────────────────────────────────────────────────────────
    
    buyer_entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("buyer_entities.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Parent buyer organization",
    )
    
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Full name",
    )
    
    role: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Job title/role",
    )
    
    department: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="e.g., Procurement, Operations, Finance",
    )
    
    # ─────────────────────────────────────────────────────────
    # Contact Information
    # ─────────────────────────────────────────────────────────
    
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Email address",
    )
    
    phone: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Direct phone number",
    )
    
    mobile: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Mobile number",
    )
    
    linkedin_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="LinkedIn profile URL",
    )
    
    # ─────────────────────────────────────────────────────────
    # Verification
    # ─────────────────────────────────────────────────────────
    
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Whether email has been verified",
    )
    
    email_verification_status: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="valid, invalid, catch-all, unknown",
    )
    
    email_verification_confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="0-100 confidence score",
    )
    
    phone_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    
    # ─────────────────────────────────────────────────────────
    # Metadata
    # ─────────────────────────────────────────────────────────
    
    source: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Where this contact was found",
    )
    
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # ─────────────────────────────────────────────────────────
    # Relationships
    # ─────────────────────────────────────────────────────────
    
    buyer_entity: Mapped[Optional["BuyerEntity"]] = relationship(
        "BuyerEntity",
        back_populates="contacts",
    )
    
    # ─────────────────────────────────────────────────────────
    # Methods
    # ─────────────────────────────────────────────────────────
    
    @property
    def is_decision_maker(self) -> bool:
        """
        Heuristic to identify if contact is likely a decision maker.
        
        Looks for keywords in role/department that suggest authority.
        """
        if not self.role:
            return False
        
        decision_keywords = [
            "director", "manager", "head", "chief", "vp", "vice",
            "procurement", "purchasing", "sourcing", "buyer",
            "owner", "founder", "ceo", "cto", "cfo", "coo"
        ]
        
        role_lower = self.role.lower()
        return any(kw in role_lower for kw in decision_keywords)
    
    def mark_email_verified(
        self,
        status: str,
        confidence: float
    ) -> None:
        """Mark email as verified with status and confidence."""
        self.email_verified = True
        self.email_verification_status = status
        self.email_verification_confidence = confidence


# Import for type hints
if TYPE_CHECKING:
    from app.models.buyer import BuyerEntity
    from sqlalchemy import Column
