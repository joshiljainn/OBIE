"""
SQLAlchemy Base Model

All models inherit from this base class which provides:
- Automatic ID generation
- Created/updated timestamps
- Soft delete support
- Utility methods
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Mixin for created/updated timestamps."""
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
    )


class SoftDeleteMixin:
    """Mixin for soft delete support."""
    
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class BaseModel(TimestampMixin, SoftDeleteMixin):
    """
    Base model for all database entities.
    
    Provides:
    - Auto-incrementing integer ID (primary key)
    - Created/updated timestamps
    - Soft delete support
    """
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True,
    )
    
    def mark_as_deleted(self) -> None:
        """Mark the record as deleted without removing from database."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
    
    def to_dict(self, exclude: list = None) -> dict:
        """
        Convert model to dictionary.
        
        Args:
            exclude: List of field names to exclude from output.
        
        Returns:
            Dictionary representation of the model.
        """
        exclude = exclude or []
        result = {}
        
        for column in self.__table__.columns:
            if column.name not in exclude:
                value = getattr(self, column.name)
                if isinstance(value, datetime):
                    value = value.isoformat()
                result[column.name] = value
        
        return result
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<{self.__class__.__name__}(id={self.id})>"
