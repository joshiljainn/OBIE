"""
Source & Source Health Models

Tracks data sources and their health metrics.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

import enum

from app.models.base import BaseModel


class SourceType(enum.Enum):
    """Type of data source."""
    
    B2B_BOARD = "b2b_board"
    TENDER = "tender"
    TRADE_SIGNAL = "trade_signal"
    CUSTOMS = "customs"
    OTHER = "other"


class SourceHealthStatus(enum.Enum):
    """Health status of a source."""
    
    HEALTHY = "healthy"  # Green - all systems operational
    DEGRADED = "degraded"  # Yellow - some issues
    DOWN = "down"  # Red - source unavailable
    UNKNOWN = "unknown"  # Gray - no data yet


class Source(BaseModel):
    """
    Data source configuration and metadata.
    
    Each source adapter (B2B, Tender, Signals) registers here.
    """
    
    __tablename__ = "sources"
    
    # ─────────────────────────────────────────────────────────
    # Identity
    # ─────────────────────────────────────────────────────────
    
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique source identifier (e.g., 'ted', 'tradekey')",
    )
    
    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable name",
    )
    
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType),
        nullable=False,
        comment="Category of source",
    )
    
    base_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Base URL for the source",
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # ─────────────────────────────────────────────────────────
    # Configuration
    # ─────────────────────────────────────────────────────────
    
    is_active: Mapped[bool] = mapped_column(
        default=True,
        comment="Whether source is enabled for ingestion",
    )
    
    priority: Mapped[int] = mapped_column(
        Integer,
        default=50,
        comment="Priority 1-100 (higher = more important)",
    )
    
    config: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON configuration for adapter",
    )
    
    # ─────────────────────────────────────────────────────────
    # Compliance
    # ─────────────────────────────────────────────────────────
    
    robots_respected: Mapped[bool] = mapped_column(
        default=True,
        comment="Whether robots.txt is respected",
    )
    
    rate_limit_per_minute: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Rate limit for this source",
    )
    
    terms_of_service_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    
    # ─────────────────────────────────────────────────────────
    # Statistics (cached/aggregated)
    # ─────────────────────────────────────────────────────────
    
    total_leads_ingested: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Total leads ever ingested",
    )
    
    total_valid_leads: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Total leads passing validation",
    )
    
    avg_intent_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Average intent score across all leads",
    )
    
    # ─────────────────────────────────────────────────────────
    # Methods
    # ─────────────────────────────────────────────────────────
    
    @property
    def validation_rate(self) -> float:
        """Calculate percentage of leads that pass validation."""
        if self.total_leads_ingested == 0:
            return 0.0
        
        return (self.total_valid_leads / self.total_leads_ingested) * 100


class SourceHealth(BaseModel):
    """
    Health metrics for a source (updated after each run).
    
    This is a time-series table tracking source performance over time.
    """
    
    __tablename__ = "source_health"
    
    # ─────────────────────────────────────────────────────────
    # Relationships
    # ─────────────────────────────────────────────────────────
    
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # ─────────────────────────────────────────────────────────
    # Run Information
    # ─────────────────────────────────────────────────────────
    
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        comment="When this health check was recorded",
    )
    
    run_duration_seconds: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="How long the ingestion run took",
    )
    
    # ─────────────────────────────────────────────────────────
    # Status
    # ─────────────────────────────────────────────────────────
    
    status: Mapped[SourceHealthStatus] = mapped_column(
        Enum(SourceHealthStatus),
        default=SourceHealthStatus.UNKNOWN,
        nullable=False,
        index=True,
    )
    
    # ─────────────────────────────────────────────────────────
    # Metrics
    # ─────────────────────────────────────────────────────────
    
    records_fetched: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Raw records fetched from source",
    )
    
    records_parsed: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Records successfully parsed",
    )
    
    records_validated: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Records passing validation",
    )
    
    records_deduped: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Records removed as duplicates",
    )
    
    parse_success_rate: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Percentage of records parsed successfully",
    )
    
    validation_success_rate: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    
    # ─────────────────────────────────────────────────────────
    # Errors
    # ─────────────────────────────────────────────────────────
    
    error_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    
    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Most recent error message",
    )
    
    last_error_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # ─────────────────────────────────────────────────────────
    # Methods
    # ─────────────────────────────────────────────────────────
    
    @classmethod
    def calculate_rates(cls, fetched: int, parsed: int, validated: int) -> dict:
        """Calculate success rates."""
        parse_rate = (parsed / fetched * 100) if fetched > 0 else 0
        validation_rate = (validated / parsed * 100) if parsed > 0 else 0
        
        return {
            "parse_success_rate": round(parse_rate, 2),
            "validation_success_rate": round(validation_rate, 2),
        }
