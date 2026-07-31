"""Index source price-bar foreign keys.

Revision ID: 4a2523700bdb
Revises: cba31be9f005
Create Date: 2026-07-30
"""

from collections.abc import Sequence

from alembic import op


revision: str = "4a2523700bdb"
down_revision: str | None = "cba31be9f005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_backtest_trades_source_price_bar_id",
        "backtest_trades",
        ["source_price_bar_id"],
    )
    op.create_index(
        "ix_paper_fills_source_price_bar_id",
        "paper_fills",
        ["source_price_bar_id"],
    )
    op.create_index(
        "ix_paper_orders_source_price_bar_id",
        "paper_orders",
        ["source_price_bar_id"],
    )
    op.create_index(
        "ix_signals_source_price_bar_id",
        "signals",
        ["source_price_bar_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_signals_source_price_bar_id", table_name="signals")
    op.drop_index("ix_paper_orders_source_price_bar_id", table_name="paper_orders")
    op.drop_index("ix_paper_fills_source_price_bar_id", table_name="paper_fills")
    op.drop_index("ix_backtest_trades_source_price_bar_id", table_name="backtest_trades")
