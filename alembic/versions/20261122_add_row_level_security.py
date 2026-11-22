"""Add PostgreSQL Row-Level Security (RLS) policies.

Guarded by dialect check so SQLite tests and offline checks pass cleanly.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261122_rls"
down_revision = "f8d30a235a4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE leads ENABLE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE leads FORCE ROW LEVEL SECURITY;")
        op.execute(
            """
            CREATE POLICY tenant_isolation_policy ON leads
            FOR ALL
            USING (
                user_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                OR NULLIF(current_setting('app.current_tenant_id', true), '') IS NULL
            )
            WITH CHECK (
                user_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                OR NULLIF(current_setting('app.current_tenant_id', true), '') IS NULL
            );
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON leads;")
        op.execute("ALTER TABLE leads DISABLE ROW LEVEL SECURITY;")
