"""
OBIE Configuration Module

Loads environment variables and provides type-safe configuration access.
"""
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # ─────────────────────────────────────────────────────────
    # Application
    # ─────────────────────────────────────────────────────────
    app_name: str = "OBIE"
    app_version: str = "2.0.0"
    env: str = "development"
    debug: bool = True
    secret_key: str = "change-me-in-production"
    
    # ─────────────────────────────────────────────────────────
    # Database
    # ─────────────────────────────────────────────────────────
    database_url: str = "postgresql://obie:obie_password@localhost:5432/obie"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    
    # ─────────────────────────────────────────────────────────
    # Redis
    # ─────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    
    # ─────────────────────────────────────────────────────────
    # Celery
    # ─────────────────────────────────────────────────────────
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_task_serializer: str = "json"
    celery_accept_content: str = "json"  # Changed from List to str
    celery_result_serializer: str = "json"
    celery_timezone: str = "UTC"
    
    # ─────────────────────────────────────────────────────────
    # API Keys
    # ─────────────────────────────────────────────────────────
    groq_api_key: Optional[str] = None
    
    # ─────────────────────────────────────────────────────────
    # Scoring
    # ─────────────────────────────────────────────────────────
    scoring_recency_weight: float = 0.25
    scoring_product_fit_weight: float = 0.20
    scoring_demand_specificity_weight: float = 0.20
    scoring_buyer_reliability_weight: float = 0.15
    scoring_contactability_weight: float = 0.10
    scoring_urgency_weight: float = 0.10
    
    scoring_s_tier_threshold: float = 85.0
    scoring_a_tier_threshold: float = 70.0
    scoring_b_tier_threshold: float = 50.0
    
    # ─────────────────────────────────────────────────────────
    # Dedupe
    # ─────────────────────────────────────────────────────────
    dedupe_fuzzy_threshold: float = 0.85
    dedupe_exact_fields: str = "url,domain"
    dedupe_fuzzy_fields: str = "buyer_name,product"
    
    # ─────────────────────────────────────────────────────────
    # Enrichment
    # ─────────────────────────────────────────────────────────
    email_verification_mode: str = "mx_only"  # none, mx_only, smtp_safe
    enrichment_max_concurrent: int = 10
    
    # ─────────────────────────────────────────────────────────
    # Rate Limiting
    # ─────────────────────────────────────────────────────────
    rate_limit_per_minute: int = 60
    request_delay: float = 1.0
    
    # ─────────────────────────────────────────────────────────
    # Logging
    # ─────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_format: str = "json"  # json, text
    log_file: str = "logs/obie.log"
    
    # ─────────────────────────────────────────────────────────
    # CORS
    # ─────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000,http://localhost:8080"
    cors_allow_credentials: bool = True
    cors_allow_methods: str = "GET,POST,PUT,DELETE,PATCH,OPTIONS"
    cors_allow_headers: str = "Authorization,Content-Type"
    
    # ─────────────────────────────────────────────────────────
    # Data Retention
    # ─────────────────────────────────────────────────────────
    data_retention_days: int = 730
    lead_auto_archive_days: int = 90
    
    # ─────────────────────────────────────────────────────────
    # Computed Properties
    # ─────────────────────────────────────────────────────────
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    @property
    def dedupe_exact_fields_list(self) -> List[str]:
        return [field.strip() for field in self.dedupe_exact_fields.split(",")]
    
    @property
    def dedupe_fuzzy_fields_list(self) -> List[str]:
        return [field.strip() for field in self.dedupe_fuzzy_fields.split(",")]
    
    @property
    def scoring_weights(self) -> dict:
        return {
            "recency": self.scoring_recency_weight,
            "product_fit": self.scoring_product_fit_weight,
            "demand_specificity": self.scoring_demand_specificity_weight,
            "buyer_reliability": self.scoring_buyer_reliability_weight,
            "contactability": self.scoring_contactability_weight,
            "urgency": self.scoring_urgency_weight,
        }
    
    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        return self.env.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Using lru_cache ensures we only load settings once
    and reuse the same instance throughout the app lifecycle.
    """
    return Settings()


# Convenience access
settings = get_settings()
