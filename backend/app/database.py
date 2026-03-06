"""
Database Configuration

Manages PostgreSQL connections using SQLAlchemy async engine.
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.pool import NullPool

from app.config import settings


# ─────────────────────────────────────────────────────────────
# Engine Configuration
# ─────────────────────────────────────────────────────────────

# Use asyncpg for async operations
engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,  # Enable connection health checks
    echo=settings.debug,  # Log SQL queries in debug mode
)

# For synchronous operations (Alembic migrations)
sync_engine = engine.sync_engine


# ─────────────────────────────────────────────────────────────
# Session Factory
# ─────────────────────────────────────────────────────────────

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ─────────────────────────────────────────────────────────────
# Base Model Class
# ─────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """
    SQLAlchemy declarative base.
    
    All models should inherit from this class.
    """
    pass


# ─────────────────────────────────────────────────────────────
# Dependency Injection
# ─────────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Database session dependency for FastAPI routes.
    
    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_db() -> AsyncGenerator[Session, None]:
    """
    Synchronous database session (for Celery tasks, scripts).
    """
    session = Session(sync_engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────────────────────

async def check_db_health() -> bool:
    """
    Check if database connection is healthy.
    
    Returns:
        True if connection is successful, False otherwise.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception:
        return False
