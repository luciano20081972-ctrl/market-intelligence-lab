from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.core.time import utc_now
from packages.database.base import Base
from packages.database.types import UTCDateTime

LEGACY_USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
LEGACY_WORKSPACE_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    auth_subject: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_disabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)


class WorkspaceMembership(Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_membership_user"),
        CheckConstraint("role IN ('owner','admin','member','viewer')", name="membership_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)


class WorkspaceInvitation(Base):
    __tablename__ = "workspace_invitations"
    __table_args__ = (
        CheckConstraint("role IN ('admin','member','viewer')", name="invitation_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(320), index=True)
    role: Mapped[str] = mapped_column(String(16))
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="RESTRICT"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    asset_type: Mapped[str] = mapped_column(String(32), index=True)
    exchange: Mapped[str] = mapped_column(String(32))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    sector: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    price_bars: Mapped[list[PriceBar]] = relationship(
        back_populates="asset", cascade="all, delete-orphan", passive_deletes=True
    )
    watchlist_links: Mapped[list[WatchlistAsset]] = relationship(
        back_populates="asset", cascade="all, delete-orphan", passive_deletes=True
    )
    metadata_versions: Mapped[list[AssetMetadataVersion]] = relationship(
        back_populates="asset", cascade="all, delete-orphan", passive_deletes=True
    )
    corporate_actions: Mapped[list[CorporateAction]] = relationship(
        back_populates="asset", cascade="all, delete-orphan", passive_deletes=True
    )


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    provider_type: Mapped[str] = mapped_column(String(50))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    health: Mapped[str] = mapped_column(String(32), default="healthy")
    last_successful_retrieval: Mapped[datetime | None] = mapped_column(UTCDateTime())
    license_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    price_bars: Mapped[list[PriceBar]] = relationship(back_populates="data_source")
    ingestion_runs: Mapped[list[DataIngestionRun]] = relationship(back_populates="data_source")


class DataIngestionRun(Base):
    __tablename__ = "data_ingestion_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    data_source: Mapped[DataSource] = relationship(back_populates="ingestion_runs")


class PriceBar(Base):
    __tablename__ = "price_bars"
    __table_args__ = (
        UniqueConstraint(
            "asset_id",
            "interval",
            "event_time",
            "data_source_id",
            name="uq_price_bar_asset_interval_event_source",
        ),
        CheckConstraint("high >= low", name="price_high_gte_low"),
        CheckConstraint("volume >= 0", name="price_volume_nonnegative"),
        Index("ix_price_bars_asset_event", "asset_id", "event_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), index=True
    )
    interval: Mapped[str] = mapped_column(String(16), default="1d")
    event_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    publication_time: Mapped[datetime] = mapped_column(UTCDateTime())
    effective_time: Mapped[datetime] = mapped_column(UTCDateTime())
    retrieval_time: Mapped[datetime] = mapped_column(UTCDateTime())
    open: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    high: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    low: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    adjusted_close: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    volume: Mapped[int] = mapped_column(Integer)
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="RESTRICT"), index=True
    )
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("providers.id", ondelete="RESTRICT"), index=True
    )
    original_symbol: Mapped[str] = mapped_column(String(32), default="", server_default="")
    adjustment_status: Mapped[str] = mapped_column(
        String(24), default="unadjusted", server_default="unadjusted"
    )
    checksum: Mapped[str] = mapped_column(String(64), default="", server_default="")
    record_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    import_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="SET NULL"), index=True
    )
    raw_provider_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default="{}"
    )
    is_demonstration_data: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    asset: Mapped[Asset] = relationship(back_populates="price_bars")
    data_source: Mapped[DataSource] = relationship(back_populates="price_bars")


class Watchlist(Base):
    __tablename__ = "watchlists"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_watchlist_workspace_name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), default=LEGACY_WORKSPACE_ID, index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    asset_links: Mapped[list[WatchlistAsset]] = relationship(
        back_populates="watchlist", cascade="all, delete-orphan", passive_deletes=True
    )


class WatchlistAsset(Base):
    __tablename__ = "watchlist_assets"
    __table_args__ = (UniqueConstraint("watchlist_id", "asset_id", name="uq_watchlist_asset_pair"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    watchlist_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("watchlists.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), index=True
    )
    added_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    watchlist: Mapped[Watchlist] = relationship(back_populates="asset_links")
    asset: Mapped[Asset] = relationship(back_populates="watchlist_links")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="SET NULL"), index=True
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[str] = mapped_column(String(24), default="success")
    correlation_id: Mapped[str | None] = mapped_column(String(80), index=True)
    ip_metadata: Mapped[str | None] = mapped_column(String(80))
    user_agent_summary: Mapped[str | None] = mapped_column(String(160))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, index=True)


class Strategy(Base):
    __tablename__ = "strategies"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_strategy_workspace_name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), default=LEGACY_WORKSPACE_ID, index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    strategy_type: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str] = mapped_column(Text)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    versions: Mapped[list[StrategyVersion]] = relationship(
        back_populates="strategy", cascade="all, delete-orphan", passive_deletes=True
    )


class StrategyVersion(Base):
    __tablename__ = "strategy_versions"
    __table_args__ = (
        UniqueConstraint("strategy_id", "version", name="uq_strategy_version_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategies.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON)
    parameter_schema: Mapped[dict[str, Any]] = mapped_column(JSON)
    calculation_notes: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    strategy: Mapped[Strategy] = relationship(back_populates="versions")
    backtest_runs: Mapped[list[BacktestRun]] = relationship(back_populates="strategy_version")


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), default=LEGACY_WORKSPACE_ID, index=True
    )
    strategy_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategy_versions.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    asset_symbols: Mapped[list[str]] = mapped_column(JSON)
    benchmark_symbol: Mapped[str] = mapped_column(String(16))
    start_time: Mapped[datetime] = mapped_column(UTCDateTime())
    end_time: Mapped[datetime] = mapped_column(UTCDateTime())
    initial_cash: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    final_equity: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    strategy_configuration: Mapped[dict[str, Any]] = mapped_column(JSON)
    risk_configuration: Mapped[dict[str, Any]] = mapped_column(JSON)
    execution_assumptions: Mapped[dict[str, Any]] = mapped_column(JSON)
    source_data_identifiers: Mapped[list[str]] = mapped_column(JSON)
    data_source_identifiers: Mapped[list[str]] = mapped_column(JSON)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    application_version: Mapped[str] = mapped_column(String(20))
    is_hypothetical: Mapped[bool] = mapped_column(Boolean, default=True)
    data_classification: Mapped[str] = mapped_column(
        String(32), default="synthetic", server_default="synthetic"
    )
    provider_identifiers: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    import_job_identifiers: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default="[]"
    )
    adjustment_statuses: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    calendar_code: Mapped[str] = mapped_column(String(32), default="XNYS", server_default="XNYS")
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    strategy_version: Mapped[StrategyVersion] = relationship(back_populates="backtest_runs")
    trades: Mapped[list[BacktestTrade]] = relationship(
        back_populates="backtest_run", cascade="all, delete-orphan", passive_deletes=True
    )
    snapshots: Mapped[list[BacktestDailySnapshot]] = relationship(
        back_populates="backtest_run", cascade="all, delete-orphan", passive_deletes=True
    )
    signals: Mapped[list[Signal]] = relationship(
        back_populates="backtest_run", cascade="all, delete-orphan", passive_deletes=True
    )


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"
    __table_args__ = (CheckConstraint("quantity > 0", name="backtest_trade_quantity_positive"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    backtest_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("backtest_runs.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True
    )
    source_price_bar_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("price_bars.id", ondelete="RESTRICT")
    )
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    side: Mapped[str] = mapped_column(String(8))
    signal_time: Mapped[datetime] = mapped_column(UTCDateTime())
    execution_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    gross_value: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    fees: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    cash_after: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    reason: Mapped[str] = mapped_column(String(160))

    backtest_run: Mapped[BacktestRun] = relationship(back_populates="trades")


class BacktestDailySnapshot(Base):
    __tablename__ = "backtest_daily_snapshots"
    __table_args__ = (
        UniqueConstraint("backtest_run_id", "event_time", name="uq_backtest_snapshot_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    backtest_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("backtest_runs.id", ondelete="CASCADE"), index=True
    )
    event_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    equity: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    cash: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    positions: Mapped[dict[str, Any]] = mapped_column(JSON)
    cumulative_fees: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    exposure: Mapped[Decimal] = mapped_column(Numeric(12, 8))
    drawdown: Mapped[Decimal] = mapped_column(Numeric(12, 8))
    benchmark_value: Mapped[Decimal] = mapped_column(Numeric(20, 6))

    backtest_run: Mapped[BacktestRun] = relationship(back_populates="snapshots")


class PaperPortfolio(Base):
    __tablename__ = "paper_portfolios"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_portfolio_workspace_name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), default=LEGACY_WORKSPACE_ID, index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    starting_cash: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    positions: Mapped[list[PaperPosition]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan", passive_deletes=True
    )
    orders: Mapped[list[PaperOrder]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan", passive_deletes=True
    )
    fills: Mapped[list[PaperFill]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan", passive_deletes=True
    )
    snapshots: Mapped[list[PortfolioSnapshot]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan", passive_deletes=True
    )
    risk_rules: Mapped[list[RiskRule]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan", passive_deletes=True
    )


class PaperPosition(Base):
    __tablename__ = "paper_positions"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "asset_id", name="uq_paper_position_asset"),
        CheckConstraint("quantity >= 0", name="paper_position_quantity_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paper_portfolios.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    average_cost: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    portfolio: Mapped[PaperPortfolio] = relationship(back_populates="positions")
    asset: Mapped[Asset] = relationship()


class PaperOrder(Base):
    __tablename__ = "paper_orders"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "client_order_id", name="uq_paper_order_client_id"),
        CheckConstraint("quantity > 0", name="paper_order_quantity_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paper_portfolios.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True
    )
    client_order_id: Mapped[str] = mapped_column(String(80))
    side: Mapped[str] = mapped_column(String(8))
    order_type: Mapped[str] = mapped_column(String(20), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    stop_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    status: Mapped[str] = mapped_column(String(24), index=True)
    is_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(300))
    estimated_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    estimated_fees: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    assumptions: Mapped[dict[str, Any]] = mapped_column(JSON)
    source_price_bar_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("price_bars.id", ondelete="RESTRICT")
    )
    submitted_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    portfolio: Mapped[PaperPortfolio] = relationship(back_populates="orders")
    asset: Mapped[Asset] = relationship()
    fills: Mapped[list[PaperFill]] = relationship(
        back_populates="order", cascade="all, delete-orphan", passive_deletes=True
    )


class PaperFill(Base):
    __tablename__ = "paper_fills"
    __table_args__ = (CheckConstraint("quantity > 0", name="paper_fill_quantity_positive"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paper_portfolios.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paper_orders.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True
    )
    source_price_bar_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("price_bars.id", ondelete="RESTRICT")
    )
    side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    gross_value: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    fees: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    filled_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)

    portfolio: Mapped[PaperPortfolio] = relationship(back_populates="fills")
    order: Mapped[PaperOrder] = relationship(back_populates="fills")
    asset: Mapped[Asset] = relationship()


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paper_portfolios.id", ondelete="CASCADE"), index=True
    )
    event_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    equity: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    cash: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    exposure: Mapped[Decimal] = mapped_column(Numeric(12, 8))
    positions: Mapped[dict[str, Any]] = mapped_column(JSON)

    portfolio: Mapped[PaperPortfolio] = relationship(back_populates="snapshots")


class RiskRule(Base):
    __tablename__ = "risk_rules"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "rule_type", name="uq_risk_rule_portfolio_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paper_portfolios.id", ondelete="CASCADE"), index=True
    )
    rule_type: Mapped[str] = mapped_column(String(64))
    limit_value: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    portfolio: Mapped[PaperPortfolio] = relationship(back_populates="risk_rules")


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    backtest_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("backtest_runs.id", ondelete="CASCADE"), index=True
    )
    strategy_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategy_versions.id", ondelete="RESTRICT"), index=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True
    )
    source_price_bar_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("price_bars.id", ondelete="RESTRICT")
    )
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    eligible_after: Mapped[datetime] = mapped_column(UTCDateTime())
    direction: Mapped[str] = mapped_column(String(16))
    strength: Mapped[Decimal] = mapped_column(Numeric(12, 8))
    explanation: Mapped[str] = mapped_column(String(500))

    backtest_run: Mapped[BacktestRun] = relationship(back_populates="signals")
    factors: Mapped[list[SignalFactor]] = relationship(
        back_populates="signal", cascade="all, delete-orphan", passive_deletes=True
    )


class SignalFactor(Base):
    __tablename__ = "signal_factors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    signal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("signals.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    value: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    signal: Mapped[Signal] = relationship(back_populates="factors")


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    adapter_type: Mapped[str] = mapped_column(String(80))
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    credential_environment_keys: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    health: Mapped[str] = mapped_column(String(32), default="disabled")
    last_tested_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_successful_import_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    credentials: Mapped[list[ProviderCredential]] = relationship(
        back_populates="provider", cascade="all, delete-orphan", passive_deletes=True
    )
    import_jobs: Mapped[list[ImportJob]] = relationship(back_populates="provider")


class ProviderCredential(Base):
    __tablename__ = "provider_credentials"
    __table_args__ = (
        UniqueConstraint("provider_id", "key_name", name="uq_provider_credential_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), index=True
    )
    key_name: Mapped[str] = mapped_column(String(80))
    secret_reference: Mapped[str] = mapped_column(String(160))
    last_four: Mapped[str | None] = mapped_column(String(4))
    is_configured: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    provider: Mapped[Provider] = relationship(back_populates="credentials")


class ImportJob(Base):
    __tablename__ = "import_jobs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "idempotency_key", name="uq_import_job_workspace_key"),
        CheckConstraint("max_attempts > 0", name="import_job_max_attempts_positive"),
        CheckConstraint("records_processed >= 0", name="import_job_processed_nonnegative"),
        CheckConstraint("records_inserted >= 0", name="import_job_inserted_nonnegative"),
        CheckConstraint("records_skipped >= 0", name="import_job_skipped_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), default=LEGACY_WORKSPACE_ID, index=True
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("providers.id", ondelete="RESTRICT"), index=True
    )
    mode: Mapped[str] = mapped_column(String(24), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    symbols: Mapped[list[str]] = mapped_column(JSON, default=list)
    request_configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resume_cursor: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, index=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    next_retry_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0)
    records_skipped: Mapped[int] = mapped_column(Integer, default=0)
    processing_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)
    validation_report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), index=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    adjustment_preference: Mapped[str] = mapped_column(
        String(24), default="unadjusted", server_default="unadjusted"
    )
    queue_name: Mapped[str] = mapped_column(
        String(32), default="manual", server_default="manual", index=True
    )

    provider: Mapped[Provider] = relationship(back_populates="import_jobs")
    batches: Mapped[list[ImportBatch]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )
    errors: Mapped[list[ImportError]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (UniqueConstraint("job_id", "sequence", name="uq_import_batch_job_sequence"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)
    request_timestamp: Mapped[datetime] = mapped_column(UTCDateTime())
    retrieval_timestamp: Mapped[datetime | None] = mapped_column(UTCDateTime())
    publication_timestamp: Mapped[datetime | None] = mapped_column(UTCDateTime())
    effective_timestamp: Mapped[datetime | None] = mapped_column(UTCDateTime())
    checksum: Mapped[str] = mapped_column(String(64))
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0)
    records_skipped: Mapped[int] = mapped_column(Integer, default=0)
    validation_report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    job: Mapped[ImportJob] = relationship(back_populates="batches")
    errors: Mapped[list[ImportError]] = relationship(back_populates="batch")


class AssetMetadataVersion(Base):
    __tablename__ = "asset_metadata_versions"
    __table_args__ = (
        UniqueConstraint("asset_id", "provider_id", "version", name="uq_asset_metadata_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), index=True
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("providers.id", ondelete="RESTRICT"), index=True
    )
    original_symbol: Mapped[str] = mapped_column(String(32))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    effective_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    retrieval_time: Mapped[datetime] = mapped_column(UTCDateTime())
    checksum: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer)

    asset: Mapped[Asset] = relationship(back_populates="metadata_versions")


class CorporateAction(Base):
    __tablename__ = "corporate_actions"
    __table_args__ = (
        UniqueConstraint("provider_id", "checksum", name="uq_corporate_action_provider_checksum"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), index=True
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("providers.id", ondelete="RESTRICT"), index=True
    )
    action_type: Mapped[str] = mapped_column(String(32), index=True)
    original_symbol: Mapped[str] = mapped_column(String(32))
    effective_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    publication_time: Mapped[datetime] = mapped_column(UTCDateTime())
    retrieval_time: Mapped[datetime] = mapped_column(UTCDateTime())
    ratio: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    currency: Mapped[str | None] = mapped_column(String(3))
    old_symbol: Mapped[str | None] = mapped_column(String(32))
    new_symbol: Mapped[str | None] = mapped_column(String(32))
    checksum: Mapped[str] = mapped_column(String(64))
    record_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="active")

    asset: Mapped[Asset] = relationship(back_populates="corporate_actions")


class ExchangeCalendar(Base):
    __tablename__ = "exchange_calendars"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(80))
    weekend_days: Mapped[list[int]] = mapped_column(JSON, default=lambda: [5, 6])
    holiday_dates: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    sessions: Mapped[list[TradingSession]] = relationship(
        back_populates="calendar", cascade="all, delete-orphan", passive_deletes=True
    )


class TradingSession(Base):
    __tablename__ = "trading_sessions"
    __table_args__ = (
        UniqueConstraint("calendar_id", "session_date", name="uq_calendar_session_date"),
        CheckConstraint("close_time > open_time", name="trading_session_close_after_open"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    calendar_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exchange_calendars.id", ondelete="CASCADE"), index=True
    )
    session_date: Mapped[str] = mapped_column(String(10), index=True)
    open_time: Mapped[datetime] = mapped_column(UTCDateTime())
    close_time: Mapped[datetime] = mapped_column(UTCDateTime())
    is_early_close: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(24), default="open")

    calendar: Mapped[ExchangeCalendar] = relationship(back_populates="sessions")


class ImportError(Base):
    __tablename__ = "import_errors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="CASCADE"), index=True
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"), index=True
    )
    error_code: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    record_identifier: Mapped[str | None] = mapped_column(String(160))
    payload_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, index=True)

    job: Mapped[ImportJob] = relationship(back_populates="errors")
    batch: Mapped[ImportBatch | None] = relationship(back_populates="errors")


class WorkerInstance(Base):
    __tablename__ = "worker_instances"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    worker_identifier: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="starting", index=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    last_heartbeat_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, index=True)
    stopped_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    current_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="SET NULL"), index=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class JobLease(Base):
    __tablename__ = "job_leases"
    __table_args__ = (CheckConstraint("expires_at > acquired_at", name="job_lease_expiry"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="CASCADE"), unique=True, index=True
    )
    worker_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("worker_instances.id", ondelete="CASCADE"), index=True
    )
    lease_token: Mapped[str] = mapped_column(String(64), unique=True)
    acquired_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    heartbeat_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class JobEvent(Base):
    __tablename__ = "job_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(48), index=True)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str | None] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, index=True)


class ImportSchedule(Base):
    __tablename__ = "import_schedules"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "provider_id", "name", name="uq_import_schedule_workspace_provider_name"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), default=LEGACY_WORKSPACE_ID, index=True
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("providers.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    scope_type: Mapped[str] = mapped_column(String(24), default="assets")
    symbols: Mapped[list[str]] = mapped_column(JSON, default=list)
    date_range_policy: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    mode: Mapped[str] = mapped_column(String(24), default="incremental")
    adjustment_preference: Mapped[str] = mapped_column(String(24), default="unadjusted")
    timezone: Mapped[str] = mapped_column(String(80), default="UTC")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    next_run_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)


class ScheduleRun(Base):
    __tablename__ = "schedule_runs"
    __table_args__ = (
        UniqueConstraint("schedule_id", "scheduled_for", name="uq_schedule_run_due_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_schedules.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="CASCADE"), unique=True, index=True
    )
    scheduled_for: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class ProviderRateLimitState(Base):
    __tablename__ = "provider_rate_limit_states"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), unique=True, index=True
    )
    requests_remaining: Mapped[int | None] = mapped_column(Integer)
    reset_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    rate_limit_events: Mapped[int] = mapped_column(Integer, default=0)
    last_response_status: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)


class ProviderSymbolMapping(Base):
    __tablename__ = "provider_symbol_mappings"
    __table_args__ = (
        UniqueConstraint("provider_id", "canonical_symbol", name="uq_provider_canonical_symbol"),
        UniqueConstraint("provider_id", "provider_symbol", name="uq_provider_external_symbol"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), index=True
    )
    canonical_symbol: Mapped[str] = mapped_column(String(32), index=True)
    provider_symbol: Mapped[str] = mapped_column(String(64), index=True)
    exchange_code: Mapped[str] = mapped_column(String(32), default="XNYS")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    records_checked: Mapped[int] = mapped_column(Integer, default=0)
    issue_count: Mapped[int] = mapped_column(Integer, default=0)
    conflict_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class ReconciliationIssue(Base):
    __tablename__ = "reconciliation_issues"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL"), index=True
    )
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL"), index=True
    )
    issue_type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    record_identifier: Mapped[str | None] = mapped_column(String(180))
    outcome: Mapped[str] = mapped_column(String(32), default="preserved")
    resolution_decision: Mapped[str] = mapped_column(String(80), default="manual_review")
    existing_checksum: Mapped[str | None] = mapped_column(String(64))
    incoming_checksum: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, index=True)


class OperationalMetric(Base):
    __tablename__ = "operational_metrics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    metric_name: Mapped[str] = mapped_column(String(80), index=True)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    labels: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="CASCADE"), index=True
    )
    worker_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("worker_instances.id", ondelete="CASCADE"), index=True
    )
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, index=True)


class ProviderHealthSnapshot(Base):
    __tablename__ = "provider_health_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    configured: Mapped[bool] = mapped_column(Boolean)
    connectivity_status: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text, default="")
    quota: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    checked_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, index=True)


class ProviderComparison(Base):
    __tablename__ = "provider_comparisons"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True
    )
    primary_provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("providers.id", ondelete="RESTRICT"), index=True
    )
    secondary_provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("providers.id", ondelete="RESTRICT"), index=True
    )
    start_time: Mapped[datetime] = mapped_column(UTCDateTime())
    end_time: Mapped[datetime] = mapped_column(UTCDateTime())
    tolerance_configuration: Mapped[dict[str, Any]] = mapped_column(JSON)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON)
    disagreements: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    resolution_status: Mapped[str] = mapped_column(String(32), default="unresolved", index=True)
    resolution_reason: Mapped[str | None] = mapped_column(Text)
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="SET NULL"), index=True
    )
    compared_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class BacktestReproducibilityManifest(Base):
    __tablename__ = "backtest_reproducibility_manifests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    backtest_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("backtest_runs.id", ondelete="CASCADE"), unique=True, index=True
    )
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON)
    manifest_checksum: Mapped[str] = mapped_column(String(64), index=True)
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class BacktestValidationReport(Base):
    __tablename__ = "backtest_validation_reports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    backtest_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("backtest_runs.id", ondelete="CASCADE"), unique=True, index=True
    )
    overall_status: Mapped[str] = mapped_column(String(24), index=True)
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    rules: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
