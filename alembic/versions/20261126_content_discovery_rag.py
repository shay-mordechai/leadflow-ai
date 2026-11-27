"""Add Brand DNA fields, categorized RAG documents, and RLS-protected content_suggestions

Revision ID: 20261126_content_discovery_rag
Revises: 20261124_add_free_tier
Create Date: 2026-11-26 21:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from src.database.models import GUID

revision: str = "20261126_content_discovery_rag"
down_revision: str | None = "20261124_add_free_tier"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Guided Brand DNA & keyword fields on business_profiles
    op.add_column("business_profiles", sa.Column("brand_style", sa.Text(), nullable=True))
    op.add_column("business_profiles", sa.Column("anti_positioning", sa.Text(), nullable=True))
    op.add_column("business_profiles", sa.Column("content_pillars", sa.JSON(), nullable=True))
    op.add_column("business_profiles", sa.Column("search_keywords", sa.JSON(), nullable=True))
    op.add_column(
        "business_profiles",
        sa.Column(
            "content_discovery_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # 2. Category separation on knowledge_documents (business_facts vs marketing_inspiration)
    op.add_column(
        "knowledge_documents",
        sa.Column(
            "category",
            sa.String(length=50),
            nullable=False,
            server_default="business_facts",
        ),
    )
    op.create_index(
        "ix_knowledge_documents_category",
        "knowledge_documents",
        ["category"],
        unique=False,
    )

    # 3. Tenant-scoped content_suggestions table with URL-hash deduplication
    op.create_table(
        "content_suggestions",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            GUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("matched_keyword", sa.String(length=150), nullable=True),
        sa.Column(
            "source_provider",
            sa.String(length=50),
            nullable=False,
            server_default="tavily",
        ),
        sa.Column("summary_he", sa.Text(), nullable=False),
        sa.Column("draft_post_he", sa.Text(), nullable=False),
        sa.Column("relevance_reason", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "ingested_document_id",
            GUID(),
            sa.ForeignKey("knowledge_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "user_id",
            "url_hash",
            name="uq_content_suggestions_user_url_hash",
        ),
    )
    op.create_index(
        "ix_content_suggestions_user_id",
        "content_suggestions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_content_suggestions_status",
        "content_suggestions",
        ["status"],
        unique=False,
    )

    # 4. Enforce PostgreSQL FORCE ROW LEVEL SECURITY and least-privilege role grants
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE content_suggestions ENABLE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE content_suggestions FORCE ROW LEVEL SECURITY;")
        op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON content_suggestions;")
        op.execute(
            """
            CREATE POLICY tenant_isolation_policy ON content_suggestions
            FOR ALL
            USING (
                user_id::text = NULLIF(current_setting('app.current_tenant_id', true), '')::text
                OR NULLIF(current_setting('app.rls_bypass', true), '') = 'on'
            )
            WITH CHECK (
                user_id::text = NULLIF(current_setting('app.current_tenant_id', true), '')::text
                OR NULLIF(current_setting('app.rls_bypass', true), '') = 'on'
            );
            """
        )
        op.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'leadflow_reader') THEN
                    GRANT SELECT ON content_suggestions TO leadflow_reader;
                END IF;
                IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'leadflow_writer') THEN
                    GRANT SELECT, INSERT, UPDATE, DELETE ON content_suggestions TO leadflow_writer;
                END IF;
            END
            $$;
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON content_suggestions;")
        op.execute("ALTER TABLE content_suggestions DISABLE ROW LEVEL SECURITY;")

    op.drop_index("ix_content_suggestions_status", table_name="content_suggestions")
    op.drop_index("ix_content_suggestions_user_id", table_name="content_suggestions")
    op.drop_table("content_suggestions")

    op.drop_index("ix_knowledge_documents_category", table_name="knowledge_documents")
    op.drop_column("knowledge_documents", "category")

    op.drop_column("business_profiles", "content_discovery_enabled")
    op.drop_column("business_profiles", "search_keywords")
    op.drop_column("business_profiles", "content_pillars")
    op.drop_column("business_profiles", "anti_positioning")
    op.drop_column("business_profiles", "brand_style")
