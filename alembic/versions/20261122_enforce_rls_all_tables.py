"""Enforce Row Level Security (RLS) and FORCE RLS on all tenant-scoped tables.

Tables: tags, phone_numbers, business_profiles, ai_agents, leads, media_interactions,
integrations, meeting_sessions, payment_transactions, audit_logs, pending_approvals,
knowledge_documents, knowledge_chunks, messages.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261122_enforce_rls_all"
down_revision = "20261122_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES_WITH_USER_ID = [
    "tags",
    "business_profiles",
    "ai_agents",
    "leads",
    "media_interactions",
    "integrations",
    "meeting_sessions",
    "payment_transactions",
    "audit_logs",
    "pending_approvals",
    "knowledge_documents",
    "knowledge_chunks",
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # 1. Tables using user_id
        for table in TABLES_WITH_USER_ID:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
            op.execute(
                f"""
                CREATE POLICY tenant_isolation_policy ON {table}
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

        # 2. phone_numbers uses owner_id
        op.execute("ALTER TABLE phone_numbers ENABLE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE phone_numbers FORCE ROW LEVEL SECURITY;")
        op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON phone_numbers;")
        op.execute(
            """
            CREATE POLICY tenant_isolation_policy ON phone_numbers
            FOR ALL
            USING (
                owner_id::text = NULLIF(current_setting('app.current_tenant_id', true), '')::text
                OR NULLIF(current_setting('app.rls_bypass', true), '') = 'on'
            )
            WITH CHECK (
                owner_id::text = NULLIF(current_setting('app.current_tenant_id', true), '')::text
                OR NULLIF(current_setting('app.rls_bypass', true), '') = 'on'
            );
            """
        )

        # 3. messages table links via lead_id -> leads
        op.execute("ALTER TABLE messages ENABLE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE messages FORCE ROW LEVEL SECURITY;")
        op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON messages;")
        op.execute(
            """
            CREATE POLICY tenant_isolation_policy ON messages
            FOR ALL
            USING (
                EXISTS (
                    SELECT 1 FROM leads
                    WHERE leads.id = messages.lead_id
                    AND leads.user_id::text = NULLIF(current_setting('app.current_tenant_id', true), '')::text
                )
                OR NULLIF(current_setting('app.rls_bypass', true), '') = 'on'
            )
            WITH CHECK (
                EXISTS (
                    SELECT 1 FROM leads
                    WHERE leads.id = messages.lead_id
                    AND leads.user_id::text = NULLIF(current_setting('app.current_tenant_id', true), '')::text
                )
                OR NULLIF(current_setting('app.rls_bypass', true), '') = 'on'
            );
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in TABLES_WITH_USER_ID + ["phone_numbers", "messages"]:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
