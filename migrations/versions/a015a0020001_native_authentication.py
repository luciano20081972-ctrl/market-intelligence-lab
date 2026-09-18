"""Add native credentials, opaque sessions and bounded rate state.

Revision ID: a015a0020001
Revises: f01500000001
"""
from alembic import op
import sqlalchemy as sa
from packages.database.types import UTCDateTime

revision = "a015a0020001"
down_revision = "f01500000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "native_credentials",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("login", sa.String(160), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_native_credentials")),
        sa.UniqueConstraint("login", name=op.f("uq_native_credentials_login")),
        sa.CheckConstraint("version > 0", name=op.f("ck_native_credentials_credential_version")),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], ondelete="RESTRICT",
            name=op.f("fk_native_credentials_user_id_user_profiles")),
    )
    op.create_table(
        "native_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("credential_version", sa.Integer(), nullable=False),
        sa.Column("issued_at", UTCDateTime(), nullable=False),
        sa.Column("last_seen_at", UTCDateTime(), nullable=False),
        sa.Column("idle_expires_at", UTCDateTime(), nullable=False),
        sa.Column("absolute_expires_at", UTCDateTime(), nullable=False),
        sa.Column("revoked_at", UTCDateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_native_sessions")),
        sa.UniqueConstraint("token_digest", name=op.f("uq_native_sessions_token_digest")),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], ondelete="RESTRICT",
            name=op.f("fk_native_sessions_user_id_user_profiles")),
    )
    op.create_index(op.f("ix_native_sessions_user_id"), "native_sessions", ["user_id"])
    op.create_index(op.f("ix_native_sessions_absolute_expires_at"), "native_sessions", ["absolute_expires_at"])
    op.create_table(
        "auth_rate_buckets",
        sa.Column("key", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_auth_rate_buckets")),
    )
    op.create_index(op.f("ix_auth_rate_buckets_expires_at"), "auth_rate_buckets", ["expires_at"])
    # Historical Supabase-hosted databases may have default Data API grants.
    # These tables must never become accessible through those roles.
    if op.get_bind().dialect.name == "postgresql":
        for table in ("native_credentials", "native_sessions", "auth_rate_buckets"):
            op.execute(f'REVOKE ALL ON TABLE "{table}" FROM PUBLIC')
            op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
            for role in ("anon", "authenticated"):
                op.execute(sa.text(f"""DO $$ BEGIN
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                        REVOKE ALL ON TABLE "{table}" FROM {role};
                    END IF;
                END $$"""))


def downgrade() -> None:
    # Intentionally refuse automated deletion of credentials/session state.
    raise RuntimeError("Native auth downgrade requires an explicit reviewed recovery plan")
