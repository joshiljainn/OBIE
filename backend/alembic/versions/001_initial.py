"""
Initial migration - Create all tables

Revision ID: initial
Create Date: 2026-03-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables."""
    
    # ─────────────────────────────────────────────────────────
    # Buyer Entities Table
    # ─────────────────────────────────────────────────────────
    op.create_table(
        "buyer_entities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("is_deleted", sa.Boolean(), default=False, nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        
        sa.Column("legal_name", sa.String(500), nullable=False, index=True),
        sa.Column("aliases", sa.Text(), nullable=True),
        sa.Column("website", sa.String(500), nullable=True, index=True),
        sa.Column("domain", sa.String(255), nullable=True, index=True),
        
        sa.Column("country", sa.String(100), nullable=True, index=True),
        sa.Column("country_name", sa.String(255), nullable=True),
        sa.Column("city", sa.String(255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        
        sa.Column("industry", sa.String(255), nullable=True),
        sa.Column("industry_codes", sa.Text(), nullable=True),
        sa.Column("company_type", sa.String(100), nullable=True),
        sa.Column("company_size", sa.String(50), nullable=True),
        
        sa.Column("phone", sa.String(100), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("linkedin_url", sa.String(500), nullable=True),
        
        sa.Column("reliability_score", sa.Float(), nullable=True),
        sa.Column("verification_status", sa.String(50), default="unverified"),
        sa.Column("source_count", sa.Integer(), default=1),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
    )
    
    # ─────────────────────────────────────────────────────────
    # Opportunities Table
    # ─────────────────────────────────────────────────────────
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("is_deleted", sa.Boolean(), default=False, nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        
        sa.Column("buyer_entity_id", sa.Integer(), sa.ForeignKey("buyer_entities.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("buyer_name_raw", sa.String(500), nullable=False),
        sa.Column("buyer_type", sa.String(100), nullable=True),
        
        sa.Column("product_text", sa.Text(), nullable=False),
        sa.Column("product_normalized", sa.String(255), nullable=True, index=True),
        sa.Column("hs_codes", sa.Text(), nullable=True),
        sa.Column("quantity_text", sa.String(255), nullable=True),
        sa.Column("quantity_value", sa.Float(), nullable=True),
        sa.Column("quantity_unit", sa.String(50), nullable=True),
        
        sa.Column("budget_text", sa.String(255), nullable=True),
        sa.Column("budget_value", sa.Float(), nullable=True),
        sa.Column("budget_currency", sa.String(10), nullable=True),
        sa.Column("incoterm", sa.String(50), nullable=True),
        
        sa.Column("destination_country", sa.String(100), nullable=True, index=True),
        sa.Column("destination_city", sa.String(255), nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        
        sa.Column("source_name", sa.String(100), nullable=False, index=True),
        sa.Column("source_url", sa.String(2000), nullable=False),
        sa.Column("source_reference_id", sa.String(255), nullable=True, index=True),
        sa.Column("raw_payload", sa.Text(), nullable=True),
        
        sa.Column("intent_score", sa.Float(), nullable=True),
        sa.Column("intent_tier", sa.String(10), nullable=True, index=True),
        sa.Column("score_breakdown", sa.Text(), nullable=True),
        
        sa.Column("status", sa.Enum("new", "reviewed", "contacted", "qualified", "disqualified", "converted", "archived", name="opportunitystatus"), default="new", nullable=False, index=True),
        sa.Column("assigned_to", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    
    # ─────────────────────────────────────────────────────────
    # Contacts Table
    # ─────────────────────────────────────────────────────────
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("is_deleted", sa.Boolean(), default=False, nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        
        sa.Column("buyer_entity_id", sa.Integer(), sa.ForeignKey("buyer_entities.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(255), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("email", sa.String(255), nullable=True, index=True),
        sa.Column("phone", sa.String(100), nullable=True),
        sa.Column("mobile", sa.String(100), nullable=True),
        sa.Column("linkedin_url", sa.String(500), nullable=True),
        
        sa.Column("email_verified", sa.Boolean(), default=False),
        sa.Column("email_verification_status", sa.String(50), nullable=True),
        sa.Column("email_verification_confidence", sa.Float(), nullable=True),
        sa.Column("phone_verified", sa.Boolean(), default=False),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    
    # ─────────────────────────────────────────────────────────
    # Opportunity-Contacts Association Table
    # ─────────────────────────────────────────────────────────
    op.create_table(
        "opportunity_contacts",
        sa.Column("opportunity_id", sa.Integer(), sa.ForeignKey("opportunities.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("is_primary", sa.Boolean(), default=False),
    )
    
    # ─────────────────────────────────────────────────────────
    # Sources Table
    # ─────────────────────────────────────────────────────────
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("is_deleted", sa.Boolean(), default=False, nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        
        sa.Column("name", sa.String(100), nullable=False, unique=True, index=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.Enum("b2b_board", "tender", "trade_signal", "customs", "other", name="sourcetype"), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("priority", sa.Integer(), default=50),
        sa.Column("config", sa.Text(), nullable=True),
        
        sa.Column("robots_respected", sa.Boolean(), default=True),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=True),
        sa.Column("terms_of_service_url", sa.String(500), nullable=True),
        
        sa.Column("total_leads_ingested", sa.Integer(), default=0),
        sa.Column("total_valid_leads", sa.Integer(), default=0),
        sa.Column("avg_intent_score", sa.Float(), nullable=True),
    )
    
    # ─────────────────────────────────────────────────────────
    # Source Health Table
    # ─────────────────────────────────────────────────────────
    op.create_table(
        "source_health",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("is_deleted", sa.Boolean(), default=False, nullable=False, index=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("run_duration_seconds", sa.Float(), nullable=True),
        
        sa.Column("status", sa.Enum("healthy", "degraded", "down", "unknown", name="sourcehealthstatus"), default="unknown", nullable=False, index=True),
        
        sa.Column("records_fetched", sa.Integer(), default=0),
        sa.Column("records_parsed", sa.Integer(), default=0),
        sa.Column("records_validated", sa.Integer(), default=0),
        sa.Column("records_deduped", sa.Integer(), default=0),
        sa.Column("parse_success_rate", sa.Float(), nullable=True),
        sa.Column("validation_success_rate", sa.Float(), nullable=True),
        
        sa.Column("error_count", sa.Integer(), default=0),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("source_health")
    op.drop_table("sources")
    op.drop_table("opportunity_contacts")
    op.drop_table("contacts")
    op.drop_table("opportunities")
    op.drop_table("buyer_entities")
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS opportunitystatus")
    op.execute("DROP TYPE IF EXISTS sourcetype")
    op.execute("DROP TYPE IF EXISTS sourcehealthstatus")
