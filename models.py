"""
Unified data models for OBIE - OSINT Buyer Intent Engine
All scrapers output to this common schema for consistency
"""
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Optional


class SourceType(Enum):
    TENDER = "tender"
    B2B_BOARD = "b2b_board"
    SOCIAL = "social"
    GOOGLE_SEARCH = "google_search"


class IntentLevel(Enum):
    CRITICAL = "critical"  # Active tender with budget + deadline
    HIGH = "high"          # Active RFQ with quantity specified
    MEDIUM = "medium"      # General buying inquiry
    LOW = "low"            # Passive interest


@dataclass
class BuyerLead:
    """
    Unified lead schema across all sources.
    
    Fields:
    - source_type: Where the lead came from (tender/b2b/social)
    - source_url: Direct link to the opportunity
    - intent_level: Critical/High/Medium/Low based on urgency
    - product: What they're buying
    - quantity: Amount/volume if specified
    - destination_country: Where goods need to be delivered
    - budget: Budget if specified (tenders usually have this)
    - deadline: Submission/response deadline
    - buyer_name: Company/organization name
    - buyer_type: Government, Private Company, NGO, etc.
    - contact_name: Person's name if available
    - contact_email: Verified email address
    - contact_phone: Phone number if available
    - description: Full opportunity description
    - requirements: Technical/compliance requirements
    - scraped_at: When this was found
    - verified: Whether contact info has been validated
    """
    source_type: str
    source_url: str
    intent_level: str
    product: str
    quantity: Optional[str] = None
    destination_country: Optional[str] = None
    budget: Optional[str] = None
    deadline: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_type: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    scraped_at: str = None
    verified: bool = False
    
    def __post_init__(self):
        if self.scraped_at is None:
            self.scraped_at = datetime.now().isoformat()
    
    def to_dict(self):
        return asdict(self)
    
    def to_csv_row(self):
        """Convert to CSV-friendly dict with consistent field order"""
        return {
            'source_type': self.source_type,
            'source_url': self.source_url,
            'intent_level': self.intent_level,
            'product': self.product,
            'quantity': self.quantity or '',
            'destination_country': self.destination_country or '',
            'budget': self.budget or '',
            'deadline': self.deadline or '',
            'buyer_name': self.buyer_name or '',
            'buyer_type': self.buyer_type or '',
            'contact_name': self.contact_name or '',
            'contact_email': self.contact_email or '',
            'contact_phone': self.contact_phone or '',
            'description': (self.description or '').replace('\n', ' ')[:500],
            'requirements': (self.requirements or '').replace('\n', ' ')[:500],
            'scraped_at': self.scraped_at,
            'verified': self.verified
        }
    
    @staticmethod
    def csv_headers():
        return [
            'source_type', 'source_url', 'intent_level', 'product',
            'quantity', 'destination_country', 'budget', 'deadline',
            'buyer_name', 'buyer_type', 'contact_name', 'contact_email',
            'contact_phone', 'description', 'requirements', 'scraped_at', 'verified'
        ]


def calculate_intent_level(
    has_budget: bool = False,
    has_deadline: bool = False,
    has_quantity: bool = False,
    is_tender: bool = False,
    days_to_deadline: Optional[int] = None
) -> str:
    """
    Calculate intent level based on available signals.
    
    Logic:
    - CRITICAL: Tender + budget + deadline (especially if <30 days)
    - HIGH: Has quantity + deadline OR quantity + destination
    - MEDIUM: Has quantity OR has destination
    - LOW: Just a general inquiry
    """
    if is_tender and has_budget and has_deadline:
        if days_to_deadline and days_to_deadline <= 30:
            return IntentLevel.CRITICAL.value
        return IntentLevel.CRITICAL.value
    
    if has_quantity and (has_deadline or days_to_deadline):
        return IntentLevel.HIGH.value
    
    if has_quantity:
        return IntentLevel.MEDIUM.value
    
    return IntentLevel.LOW.value
