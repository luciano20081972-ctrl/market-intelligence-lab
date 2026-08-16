"""reconcile legacy Phase-5 production with the official v0.14 history

Revision ID: a141c0de0001
Revises: 3b2f6c7d8e90, 5595df1fe1cf
Create Date: 2026-08-15

The Phase-5 branch was executed by the home-server production database. Its
tables remain intact as read-only legacy operational history. The official
v0.14 branch uses distinct table names, so no destructive convergence is
required at this boundary.
"""

from collections.abc import Sequence

revision: str = "a141c0de0001"
down_revision: tuple[str, str] = ("3b2f6c7d8e90", "5595df1fe1cf")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the proven-compatible histories without changing preserved data."""


def downgrade() -> None:
    raise RuntimeError(
        "v0.14.1 reconciliation is forward-only; restore the verified "
        "pre-deployment database snapshot to roll back"
    )
