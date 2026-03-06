"""
Source Adapter Interface

Abstract base class defining the contract for all data source adapters.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class LeadSignal:
    """
    Raw lead signal from a source.
    
    This is the output of adapter.parse() and input to the
    normalization pipeline. All sources must map to this schema.
    """
    
    # ─────────────────────────────────────────────────────────
    # Required Fields (no defaults)
    # ─────────────────────────────────────────────────────────
    
    source_name: str
    """Adapter name (e.g., 'tradekey', 'ted', 'reddit')"""
    
    source_url: str
    """Direct URL to the opportunity/listing"""
    
    buyer_name: str
    """Raw buyer name from source"""
    
    product_text: str
    """Raw product description"""
    
    # ─────────────────────────────────────────────────────────
    # Optional Fields (with defaults)
    # ─────────────────────────────────────────────────────────
    
    source_reference_id: Optional[str] = None
    """Source's internal ID (for dedupe)"""
    
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    """When this was fetched"""
    
    published_at: Optional[datetime] = None
    """When the opportunity was published"""
    
    buyer_type: Optional[str] = None
    """e.g., 'Importer', 'Distributor', 'Government'"""
    
    quantity_text: Optional[str] = None
    """Raw quantity (e.g., '500 tons', '10 containers')"""
    
    location_text: Optional[str] = None
    """Raw location/destination"""
    
    budget_text: Optional[str] = None
    """Raw budget text"""
    
    deadline_text: Optional[str] = None
    """Raw deadline text"""
    
    contact_text: Optional[str] = None
    """Raw contact information"""
    
    description: Optional[str] = None
    """Full description/summary"""
    
    raw_payload: Dict[str, Any] = field(default_factory=dict)
    """Complete raw data from source"""
    
    raw_html_excerpt: Optional[str] = None
    """HTML excerpt (if scraped)"""
    
    parser_version: str = "1.0"
    """Parser version for reproducibility"""
    
    extraction_confidence: float = 1.0
    """0-1 confidence in extraction quality"""
    
    def validate(self) -> tuple[bool, List[str]]:
        """
        Validate the lead signal has minimum required fields.
        
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        
        if not self.source_name:
            errors.append("source_name is required")
        
        if not self.source_url:
            errors.append("source_url is required")
        
        if not self.buyer_name:
            errors.append("buyer_name is required")
        
        if not self.product_text:
            errors.append("product_text is required")
        
        return (len(errors) == 0, errors)


class SourceAdapter(ABC):
    """
    Abstract base class for all source adapters.
    
    Adapters are responsible for:
    1. Fetching data from a source (API, RSS, scrape)
    2. Parsing into LeadSignal objects
    3. Handling errors, rate limiting, retries
    
    Adapters should NOT:
    - Normalize data (done in pipeline)
    - Score leads (done in scoring engine)
    - Store to database (done in ingestion service)
    """
    
    # ─────────────────────────────────────────────────────────
    # Class Configuration (override in subclasses)
    # ─────────────────────────────────────────────────────────
    
    SOURCE_NAME: str = "base"
    """Unique identifier for this source"""
    
    SOURCE_DISPLAY_NAME: str = "Base Source"
    """Human-readable name"""
    
    SOURCE_TYPE: str = "other"
    """Category: b2b_board, tender, trade_signal, customs"""
    
    RATE_LIMIT_PER_MINUTE: int = 60
    """Rate limit for this source"""
    
    REQUEST_DELAY: float = 1.0
    """Delay between requests (seconds)"""
    
    # ─────────────────────────────────────────────────────────
    # Abstract Methods (must implement)
    # ─────────────────────────────────────────────────────────
    
    @abstractmethod
    async def fetch(self, config: Dict[str, Any]) -> List[Any]:
        """
        Fetch raw data from the source.
        
        Args:
            config: Source-specific configuration (keywords, URLs, etc.)
        
        Returns:
            List of raw data items (dicts, HTML, etc.)
        
        Raises:
            SourceError: If fetch fails
        """
        pass
    
    @abstractmethod
    async def parse(self, raw_data: Any) -> List[LeadSignal]:
        """
        Parse raw data into LeadSignal objects.
        
        Args:
            raw_data: Raw data from fetch()
        
        Returns:
            List of LeadSignal objects
        
        Raises:
            ParseError: If parsing fails
        """
        pass
    
    # ─────────────────────────────────────────────────────────
    # Hook Methods (override as needed)
    # ─────────────────────────────────────────────────────────
    
    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate configuration before fetching.
        
        Override to add source-specific validation.
        
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        return (True, [])
    
    def normalize_url(self, url: str) -> str:
        """
        Normalize URL for dedupe comparison.
        
        Override for source-specific URL normalization.
        """
        return url.strip().lower()
    
    # ─────────────────────────────────────────────────────────
    # Utility Methods
    # ─────────────────────────────────────────────────────────
    
    def create_lead_signal(
        self,
        buyer_name: str,
        product_text: str,
        source_url: str,
        **kwargs
    ) -> LeadSignal:
        """
        Factory method to create LeadSignal with source defaults.
        """
        return LeadSignal(
            source_name=self.SOURCE_NAME,
            buyer_name=buyer_name,
            product_text=product_text,
            source_url=source_url,
            **kwargs
        )
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get adapter metadata for registration."""
        return {
            "name": self.SOURCE_NAME,
            "display_name": self.SOURCE_DISPLAY_NAME,
            "source_type": self.SOURCE_TYPE,
            "rate_limit": self.RATE_LIMIT_PER_MINUTE,
            "request_delay": self.REQUEST_DELAY,
        }


# ─────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────

class SourceError(Exception):
    """Base exception for source errors."""
    pass


class FetchError(SourceError):
    """Error fetching data from source."""
    pass


class ParseError(SourceError):
    """Error parsing source data."""
    pass


class RateLimitError(SourceError):
    """Rate limit exceeded."""
    pass


class AuthenticationError(SourceError):
    """Authentication failed."""
    pass
