from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
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
        ForeignKey("price_bars.id", ondelete="RESTRICT"), index=True
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
        ForeignKey("price_bars.id", ondelete="RESTRICT"), index=True
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
        ForeignKey("price_bars.id", ondelete="RESTRICT"), index=True
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
        ForeignKey("price_bars.id", ondelete="RESTRICT"), index=True
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


class DataManifest(Base):
    """Immutable provenance envelope for one acquired dataset object."""

    __tablename__ = "data_manifests"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "dataset_id", "checksum", name="uq_manifest_dataset_checksum"
        ),
        CheckConstraint("record_count >= 0", name="manifest_record_count_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    dataset_id: Mapped[str] = mapped_column(String(96), index=True)
    source_version: Mapped[str | None] = mapped_column(String(80))
    schema_version: Mapped[str] = mapped_column(String(32), default="1")
    parser_version: Mapped[str] = mapped_column(String(40))
    retrieval_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    source_updated_time: Mapped[datetime | None] = mapped_column(UTCDateTime())
    temporal_coverage_start: Mapped[datetime | None] = mapped_column(UTCDateTime())
    temporal_coverage_end: Mapped[datetime | None] = mapped_column(UTCDateTime())
    raw_object_reference: Mapped[str] = mapped_column(String(700))
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    checksum_algorithm: Mapped[str] = mapped_column(String(16), default="sha256")
    byte_count: Mapped[int] = mapped_column(Integer, default=0)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    quality_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    license_identifier: Mapped[str] = mapped_column(String(120))
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="SET NULL"), index=True
    )
    parent_manifest_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_manifests.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class RawDataObject(Base):
    __tablename__ = "raw_data_objects"

    key: Mapped[str] = mapped_column(String(700), primary_key=True)
    checksum: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    byte_count: Mapped[int] = mapped_column(Integer)
    media_type: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class MacroSeries(Base):
    __tablename__ = "macro_series"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_macro_source_external"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(300))
    units: Mapped[str] = mapped_column(String(120))
    frequency: Mapped[str] = mapped_column(String(80))
    seasonal_adjustment: Mapped[str | None] = mapped_column(String(120))
    release_id: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime())


class MacroObservation(Base):
    __tablename__ = "macro_observations"
    __table_args__ = (
        UniqueConstraint(
            "series_id",
            "observation_time",
            "revision_time",
            "source_value",
            name="uq_macro_observation_vintage",
        ),
        Index("ix_macro_as_of", "series_id", "observation_time", "simulation_eligible_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    series_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("macro_series.id", ondelete="CASCADE"), index=True
    )
    source_value: Mapped[str] = mapped_column(String(120))
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    event_time: Mapped[datetime] = mapped_column(UTCDateTime())
    observation_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    publication_time: Mapped[datetime] = mapped_column(UTCDateTime())
    retrieval_time: Mapped[datetime] = mapped_column(UTCDateTime())
    effective_time: Mapped[datetime] = mapped_column(UTCDateTime())
    revision_time: Mapped[datetime] = mapped_column(UTCDateTime())
    simulation_eligible_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    realtime_end: Mapped[datetime | None] = mapped_column(UTCDateTime())
    time_precision: Mapped[str] = mapped_column(String(24), default="day")
    source_time_zone: Mapped[str] = mapped_column(String(64), default="UTC")
    quality_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    manifest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_manifests.id", ondelete="RESTRICT"), index=True
    )


class EnergySeries(Base):
    __tablename__ = "energy_series"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_energy_source_external"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str] = mapped_column(String(180), index=True)
    title: Mapped[str] = mapped_column(String(300))
    units: Mapped[str] = mapped_column(String(120))
    frequency: Mapped[str] = mapped_column(String(80))
    geography: Mapped[str] = mapped_column(String(120))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime())


class EnergyObservation(Base):
    __tablename__ = "energy_observations"
    __table_args__ = (
        UniqueConstraint(
            "series_id", "observation_time", "source_value", name="uq_energy_observation"
        ),
        Index("ix_energy_series_observation", "series_id", "observation_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    series_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("energy_series.id", ondelete="CASCADE"), index=True
    )
    source_value: Mapped[str] = mapped_column(String(120))
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    event_time: Mapped[datetime] = mapped_column(UTCDateTime())
    observation_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    publication_time: Mapped[datetime] = mapped_column(UTCDateTime())
    retrieval_time: Mapped[datetime] = mapped_column(UTCDateTime())
    effective_time: Mapped[datetime] = mapped_column(UTCDateTime())
    revision_time: Mapped[datetime] = mapped_column(UTCDateTime())
    simulation_eligible_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    time_precision: Mapped[str] = mapped_column(String(24), default="month")
    source_time_zone: Mapped[str] = mapped_column(String(64), default="UTC")
    quality_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    manifest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_manifests.id", ondelete="RESTRICT"), index=True
    )


class IngestionCheckpoint(Base):
    __tablename__ = "ingestion_checkpoints"
    __table_args__ = (UniqueConstraint("source_id", "dataset_id", name="uq_checkpoint_dataset"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    dataset_id: Mapped[str] = mapped_column(String(96), index=True)
    cursor_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    last_manifest_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_manifests.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)


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


class SecCompany(Base):
    __tablename__ = "sec_companies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cik: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(240), index=True)
    tickers: Mapped[list[str]] = mapped_column(JSON, default=list)
    sic: Mapped[str | None] = mapped_column(String(8))
    submissions_url: Mapped[str] = mapped_column(String(500))
    facts_url: Mapped[str] = mapped_column(String(500))
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    source_checksum: Mapped[str] = mapped_column(String(64), index=True)


class SecFiling(Base):
    __tablename__ = "sec_filings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sec_companies.id", ondelete="CASCADE"), index=True
    )
    accession_number: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    form_type: Mapped[str] = mapped_column(String(16), index=True)
    filing_date: Mapped[date] = mapped_column(Date, index=True)
    accepted_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    reporting_period: Mapped[date | None] = mapped_column(Date)
    source_url: Mapped[str] = mapped_column(String(700))
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    content_checksum: Mapped[str] = mapped_column(String(64), index=True)
    raw_document_reference: Mapped[str] = mapped_column(String(500))
    parser_version: Mapped[str] = mapped_column(String(40))
    edgartools_version: Mapped[str] = mapped_column(String(40))
    is_amendment: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    simulation_eligible_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


class SecDocument(Base):
    __tablename__ = "sec_documents"
    __table_args__ = (
        UniqueConstraint("filing_id", "sequence", name="uq_sec_document_filing_sequence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filing_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sec_filings.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    document_type: Mapped[str] = mapped_column(String(40), index=True)
    source_url: Mapped[str] = mapped_column(String(700))
    content_reference: Mapped[str] = mapped_column(String(500))
    content_checksum: Mapped[str] = mapped_column(String(64), index=True)


class SecFact(Base):
    __tablename__ = "sec_facts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sec_companies.id", ondelete="CASCADE"), index=True
    )
    filing_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sec_filings.id", ondelete="CASCADE"), index=True
    )
    taxonomy: Mapped[str] = mapped_column(String(40), index=True)
    concept: Mapped[str] = mapped_column(String(160), index=True)
    unit: Mapped[str] = mapped_column(String(32))
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(28, 8))
    text_value: Mapped[str | None] = mapped_column(Text)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    filed_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


class SecInsiderTransaction(Base):
    __tablename__ = "sec_insider_transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sec_companies.id", ondelete="CASCADE"), index=True
    )
    filing_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sec_filings.id", ondelete="CASCADE"), index=True
    )
    owner_name: Mapped[str] = mapped_column(String(240), index=True)
    relationship: Mapped[str] = mapped_column(String(120))
    transaction_code: Mapped[str] = mapped_column(String(8))
    security_title: Mapped[str] = mapped_column(String(160))
    transaction_date: Mapped[date] = mapped_column(Date, index=True)
    shares: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    acquired_disposed: Mapped[str] = mapped_column(String(1))


class SecInstitutionalHolding(Base):
    __tablename__ = "sec_institutional_holdings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filing_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sec_filings.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sec_companies.id", ondelete="SET NULL"), index=True
    )
    issuer_name: Mapped[str] = mapped_column(String(240), index=True)
    cusip: Mapped[str] = mapped_column(String(12), index=True)
    as_of_date: Mapped[date] = mapped_column(Date, index=True)
    shares: Mapped[Decimal] = mapped_column(Numeric(24, 4))
    value_usd: Mapped[Decimal] = mapped_column(Numeric(24, 2))
    voting_authority: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SecIngestionJob(Base):
    __tablename__ = "sec_ingestion_jobs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "idempotency_key", name="uq_sec_ingestion_workspace_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="RESTRICT"), index=True
    )
    cik: Mapped[str] = mapped_column(String(10), index=True)
    forms: Mapped[list[str]] = mapped_column(JSON, default=list)
    mode: Mapped[str] = mapped_column(String(20), default="fixture")
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120))
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class SecParseResult(Base):
    __tablename__ = "sec_parse_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ingestion_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sec_ingestion_jobs.id", ondelete="CASCADE"), index=True
    )
    filing_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sec_filings.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), index=True)
    parser_version: Mapped[str] = mapped_column(String(40))
    parser_checksum: Mapped[str] = mapped_column(String(64))
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    parsed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class AnalyticsComparisonRecord(Base):
    __tablename__ = "analytics_comparison_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    return_series_checksum: Mapped[str] = mapped_column(String(64), index=True)
    benchmark: Mapped[str | None] = mapped_column(String(32))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    canonical_metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    adapter_metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    reconciliation: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    methodology_notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    engine_versions: Mapped[dict[str, str]] = mapped_column(JSON)
    agreement_status: Mapped[str] = mapped_column(String(24), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class OptimizationExperiment(Base):
    __tablename__ = "optimization_experiments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    model: Mapped[str] = mapped_column(String(48), index=True)
    hyperparameters: Mapped[dict[str, Any]] = mapped_column(JSON)
    asset_universe: Mapped[list[str]] = mapped_column(JSON)
    input_return_checksum: Mapped[str] = mapped_column(String(64), index=True)
    covariance_estimator: Mapped[dict[str, Any]] = mapped_column(JSON)
    expected_return_estimator: Mapped[dict[str, Any]] = mapped_column(JSON)
    constraints: Mapped[dict[str, Any]] = mapped_column(JSON)
    training_period: Mapped[dict[str, str]] = mapped_column(JSON)
    validation_period: Mapped[dict[str, str]] = mapped_column(JSON)
    resulting_weights: Mapped[dict[str, float]] = mapped_column(JSON)
    objective_values: Mapped[dict[str, float]] = mapped_column(JSON)
    risk_metrics: Mapped[dict[str, float]] = mapped_column(JSON)
    optimizer_version: Mapped[str] = mapped_column(String(40))
    random_seed: Mapped[int] = mapped_column(Integer)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class ExternalEngineRun(Base):
    __tablename__ = "external_engine_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    engine: Mapped[str] = mapped_column(String(40), index=True)
    engine_version: Mapped[str] = mapped_column(String(80))
    engine_commit: Mapped[str | None] = mapped_column(String(64))
    request_checksum: Mapped[str] = mapped_column(String(64), index=True)
    request_manifest: Mapped[dict[str, Any]] = mapped_column(JSON)
    result_manifest: Mapped[dict[str, Any]] = mapped_column(JSON)
    comparison: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), index=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class EconomicEntity(Base):
    """Workspace-scoped canonical node in the economic driver graph."""

    __tablename__ = "economic_entities"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "entity_type", "normalized_name", name="uq_economic_entity_identity"
        ),
        CheckConstraint(
            "status IN ('candidate','verified','disputed','expired','rejected')",
            name="economic_entity_status_valid",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="economic_entity_confidence_range"
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name="economic_entity_valid_range"
        ),
        Index(
            "ix_economic_entity_workspace_type_status",
            "workspace_id",
            "entity_type",
            "status",
        ),
        Index(
            "ix_economic_entity_workspace_eligible",
            "workspace_id",
            "simulation_eligible_time",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(48), index=True)
    canonical_name: Mapped[str] = mapped_column(String(300), index=True)
    normalized_name: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(24), default="candidate", index=True)
    valid_from: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    valid_to: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    first_seen: Mapped[datetime] = mapped_column(UTCDateTime())
    last_verified: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    event_time: Mapped[datetime] = mapped_column(UTCDateTime())
    observation_time: Mapped[datetime] = mapped_column(UTCDateTime())
    publication_time: Mapped[datetime] = mapped_column(UTCDateTime())
    retrieval_time: Mapped[datetime] = mapped_column(UTCDateTime())
    effective_time: Mapped[datetime] = mapped_column(UTCDateTime())
    revision_time: Mapped[datetime] = mapped_column(UTCDateTime())
    simulation_eligible_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    time_precision: Mapped[str] = mapped_column(String(24), default="second")
    source_time_zone: Mapped[str] = mapped_column(String(64), default="UTC")
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), default=Decimal("1"))
    source_manifest_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_manifests.id", ondelete="RESTRICT"), index=True
    )
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)


class EntityIdentifier(Base):
    __tablename__ = "entity_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "namespace", "normalized_value", name="uq_entity_identifier_value"
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="entity_identifier_confidence_range"
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name="entity_identifier_valid_range"
        ),
        Index("ix_entity_identifier_entity_namespace", "entity_id", "namespace"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("economic_entities.id", ondelete="CASCADE"), index=True
    )
    namespace: Mapped[str] = mapped_column(String(48), index=True)
    value: Mapped[str] = mapped_column(String(240))
    normalized_value: Mapped[str] = mapped_column(String(240), index=True)
    mapping_method: Mapped[str] = mapped_column(String(48))
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    source: Mapped[str] = mapped_column(String(120))
    evidence_reference: Mapped[str | None] = mapped_column(String(700))
    resolver_version: Mapped[str] = mapped_column(String(40))
    resolved_at: Mapped[datetime] = mapped_column(UTCDateTime())
    valid_from: Mapped[datetime] = mapped_column(UTCDateTime())
    valid_to: Mapped[datetime | None] = mapped_column(UTCDateTime())
    simulation_eligible_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


# Architectural name retained for callers and documentation; the concise model name remains
# backward-compatible with the v0.8 implementation modules.
ExternalIdentifier = EntityIdentifier


class EntityAlias(Base):
    __tablename__ = "entity_aliases"
    __table_args__ = (
        UniqueConstraint("entity_id", "normalized_alias", name="uq_entity_alias_entity_value"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("economic_entities.id", ondelete="CASCADE"), index=True
    )
    alias: Mapped[str] = mapped_column(String(300))
    normalized_alias: Mapped[str] = mapped_column(String(300), index=True)
    source: Mapped[str] = mapped_column(String(120))
    valid_from: Mapped[datetime] = mapped_column(UTCDateTime())
    valid_to: Mapped[datetime | None] = mapped_column(UTCDateTime())
    simulation_eligible_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


class EntityResolutionCandidate(Base):
    __tablename__ = "entity_resolution_candidates"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "namespace",
            "normalized_value",
            "candidate_entity_id",
            name="uq_resolution_candidate_mapping",
        ),
        CheckConstraint(
            "status IN ('candidate','confirmed','rejected','ambiguous')",
            name="status_valid",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    namespace: Mapped[str] = mapped_column(String(48), index=True)
    value: Mapped[str] = mapped_column(String(240))
    normalized_value: Mapped[str] = mapped_column(String(240), index=True)
    candidate_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("economic_entities.id", ondelete="CASCADE"), index=True
    )
    method: Mapped[str] = mapped_column(String(48))
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    source: Mapped[str] = mapped_column(String(120))
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resolver_version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), default="candidate", index=True)
    resolved_at: Mapped[datetime] = mapped_column(UTCDateTime())
    valid_from: Mapped[datetime] = mapped_column(UTCDateTime())
    valid_to: Mapped[datetime | None] = mapped_column(UTCDateTime())
    simulation_eligible_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


class EntityResolutionDecision(Base):
    __tablename__ = "entity_resolution_decisions"
    __table_args__ = (
        UniqueConstraint("candidate_id", name="uq_resolution_decision_candidate"),
        CheckConstraint(
            "decision IN ('confirmed','rejected')", name="resolution_decision_value_valid"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity_resolution_candidates.id", ondelete="CASCADE"), index=True
    )
    decision: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str] = mapped_column(Text)
    decided_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="RESTRICT"), index=True
    )
    decided_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class EconomicRelationship(Base):
    __tablename__ = "economic_relationships"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "subject_entity_id",
            "predicate",
            "object_entity_id",
            "valid_from",
            name="uq_economic_relationship_version",
        ),
        CheckConstraint(
            "subject_entity_id <> object_entity_id", name="economic_relationship_not_self"
        ),
        CheckConstraint(
            "status IN ('candidate','verified','disputed','expired','rejected')",
            name="economic_relationship_status_valid",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint(
            "strength IS NULL OR (strength >= 0 AND strength <= 1)",
            name="economic_relationship_strength_range",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name="economic_relationship_valid_range"
        ),
        Index(
            "ix_economic_relationship_outbound",
            "workspace_id",
            "subject_entity_id",
            "status",
            "simulation_eligible_time",
        ),
        Index(
            "ix_economic_relationship_inbound",
            "workspace_id",
            "object_entity_id",
            "status",
            "simulation_eligible_time",
        ),
        Index(
            "ix_economic_relationship_predicate_subject",
            "workspace_id",
            "predicate",
            "subject_entity_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    subject_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("economic_entities.id", ondelete="CASCADE"), index=True
    )
    predicate: Mapped[str] = mapped_column(String(48), index=True)
    object_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("economic_entities.id", ondelete="CASCADE"), index=True
    )
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    strength: Mapped[Decimal | None] = mapped_column(Numeric(6, 5))
    valid_from: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    valid_to: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    discovered_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_verified_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    simulation_eligible_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    method: Mapped[str] = mapped_column(String(64))
    method_version: Mapped[str] = mapped_column(String(40))
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="candidate", index=True)


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "checksum", "source_record_identifier", name="uq_evidence_source"
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="evidence_confidence_range"),
        Index("ix_evidence_workspace_eligible", "workspace_id", "simulation_eligible_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    source_manifest_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_manifests.id", ondelete="RESTRICT"), index=True
    )
    sec_filing_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sec_filings.id", ondelete="RESTRICT"), index=True
    )
    source_record_identifier: Mapped[str] = mapped_column(String(300), index=True)
    source_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("economic_entities.id", ondelete="SET NULL"), index=True
    )
    publication_time: Mapped[datetime] = mapped_column(UTCDateTime())
    simulation_eligible_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    evidence_type: Mapped[str] = mapped_column(String(48), index=True)
    structured_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    content_reference: Mapped[str | None] = mapped_column(String(700))
    supporting_text: Mapped[str | None] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    parser_version: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class RelationshipEvidence(Base):
    __tablename__ = "relationship_evidence"
    __table_args__ = (
        UniqueConstraint(
            "relationship_id", "evidence_id", "direction", name="uq_relationship_evidence_link"
        ),
        CheckConstraint(
            "direction IN ('supporting','contradicting')", name="relationship_evidence_direction"
        ),
        CheckConstraint("weight >= 0 AND weight <= 1", name="relationship_evidence_weight_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    relationship_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("economic_relationships.id", ondelete="CASCADE"), index=True
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_records.id", ondelete="CASCADE"), index=True
    )
    direction: Mapped[str] = mapped_column(String(24))
    weight: Mapped[Decimal] = mapped_column(Numeric(6, 5), default=Decimal("1"))


class RelationshipConfidenceComponent(Base):
    __tablename__ = "relationship_confidence_components"
    __table_args__ = (
        UniqueConstraint(
            "relationship_id", "formula_version", "component", name="uq_relationship_confidence"
        ),
        CheckConstraint("value >= 0 AND value <= 1", name="component_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    relationship_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("economic_relationships.id", ondelete="CASCADE"), index=True
    )
    formula_version: Mapped[str] = mapped_column(String(32))
    component: Mapped[str] = mapped_column(String(48))
    value: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    rationale: Mapped[str] = mapped_column(Text)


class CompanyDriverProfile(Base):
    __tablename__ = "company_driver_profiles"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "company_entity_id", "version", name="uq_company_driver_profile_version"
        ),
        Index(
            "ix_company_driver_profile_latest", "workspace_id", "company_entity_id", "generated_at"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    company_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("economic_entities.id", ondelete="CASCADE"), index=True
    )
    prior_version: Mapped[str] = mapped_column(String(40))
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    version: Mapped[int] = mapped_column(Integer)
    simulation_eligible_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    trigger_reason: Mapped[str] = mapped_column(String(120))


class CompanyDriverEntry(Base):
    __tablename__ = "company_driver_entries"
    __table_args__ = (
        UniqueConstraint("profile_id", "driver_category", name="uq_driver_entry_profile_category"),
        CheckConstraint("prior_relevance >= 0 AND prior_relevance <= 1", name="driver_prior_range"),
        CheckConstraint(
            "evidence_relevance >= 0 AND evidence_relevance <= 1", name="driver_evidence_range"
        ),
        CheckConstraint(
            "effective_relevance >= 0 AND effective_relevance <= 1",
            name="driver_effective_range",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="driver_confidence_range"),
        Index("ix_driver_entry_profile_relevance", "profile_id", "effective_relevance"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("company_driver_profiles.id", ondelete="CASCADE"), index=True
    )
    driver_category: Mapped[str] = mapped_column(String(48), index=True)
    linked_entity_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    supporting_relationship_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    prior_relevance: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    evidence_relevance: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    historical_evidence_relevance: Mapped[Decimal | None] = mapped_column(Numeric(6, 5))
    user_override: Mapped[Decimal | None] = mapped_column(Numeric(6, 5))
    effective_relevance: Mapped[Decimal] = mapped_column(Numeric(6, 5), index=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    explanation: Mapped[str] = mapped_column(Text)


class DataRelevanceDecision(Base):
    __tablename__ = "data_relevance_decisions"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "dataset_id", "router_version", name="uq_data_relevance_version"
        ),
        CheckConstraint(
            "decision IN ('PROCESS','DEFER','IGNORE','REVIEW')",
            name="data_relevance_decision_valid",
        ),
        CheckConstraint("relevance_score >= 0 AND relevance_score <= 1", name="route_score_range"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="route_confidence_range"),
        Index("ix_data_relevance_company_created", "company_entity_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("company_driver_profiles.id", ondelete="CASCADE"), index=True
    )
    company_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("economic_entities.id", ondelete="CASCADE"), index=True
    )
    dataset_id: Mapped[str] = mapped_column(String(120), index=True)
    decision: Mapped[str] = mapped_column(String(16), index=True)
    relevance_score: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    supporting_graph_paths: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    router_version: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class GraphQualityIssue(Base):
    __tablename__ = "graph_quality_issues"
    __table_args__ = (
        CheckConstraint(
            "issue_type IN ('orphan_entity','duplicate_candidate','ambiguous_identifier',"
            "'expired_relationship','missing_evidence','conflicting_evidence','low_confidence',"
            "'stale_verification','temporal_inconsistency','cycle_anomaly')",
            name="graph_quality_issue_type_valid",
        ),
        CheckConstraint(
            "status IN ('open','acknowledged','resolved')", name="graph_quality_status_valid"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    issue_type: Mapped[str] = mapped_column(String(48), index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("economic_entities.id", ondelete="CASCADE"), index=True
    )
    relationship_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("economic_relationships.id", ondelete="CASCADE"), index=True
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    detected_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class GraphRecomputeJob(Base):
    __tablename__ = "graph_recompute_jobs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "idempotency_key", name="uq_graph_recompute_workspace_key"
        ),
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')",
            name="graph_recompute_status_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    company_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("economic_entities.id", ondelete="CASCADE"), index=True
    )
    trigger_reason: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, index=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    error_message: Mapped[str | None] = mapped_column(Text)


class ResearchUniverse(Base):
    __tablename__ = "research_universes"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_research_universe_name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    owner_type: Mapped[str] = mapped_column(String(16), default="workspace")
    source: Mapped[str] = mapped_column(String(160))
    selection_rules: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class ResearchUniverseVersion(Base):
    __tablename__ = "research_universe_versions"
    __table_args__ = (
        UniqueConstraint("universe_id", "version", name="uq_research_universe_version"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from", name="universe_version_range"
        ),
        Index(
            "ix_universe_version_as_of", "universe_id", "simulation_eligible_time", "effective_from"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    universe_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_universes.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    effective_from: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    effective_to: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    simulation_eligible_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    membership_checksum: Mapped[str] = mapped_column(String(64))
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class ResearchUniverseMembership(Base):
    __tablename__ = "research_universe_memberships"
    __table_args__ = (
        UniqueConstraint("universe_version_id", "entity_id", name="uq_universe_membership_entity"),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name="universe_membership_range"
        ),
        Index(
            "ix_universe_membership_as_of",
            "universe_version_id",
            "simulation_eligible_time",
            "valid_from",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    universe_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_universe_versions.id", ondelete="CASCADE"), index=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("economic_entities.id", ondelete="CASCADE"), index=True
    )
    valid_from: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    valid_to: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    simulation_eligible_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    source_manifest_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_manifests.id", ondelete="RESTRICT"), index=True
    )
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class FeatureDefinition(Base):
    __tablename__ = "feature_definitions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "feature_key", name="uq_feature_definition_key"),
        CheckConstraint(
            "status IN ('draft','active','deprecated','disabled')", name="feature_definition_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    feature_key: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(40), index=True)
    entity_type: Mapped[str] = mapped_column(String(48), default="Company")
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class FeatureDefinitionVersion(Base):
    __tablename__ = "feature_definition_versions"
    __table_args__ = (
        UniqueConstraint("feature_definition_id", "version", name="uq_feature_definition_version"),
        CheckConstraint(
            "cost_class IN ('free','low','medium','high','premium')", name="feature_version_cost"
        ),
        CheckConstraint(
            "determinism IN ('deterministic','non_deterministic')",
            name="feature_version_determinism",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    feature_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feature_definitions.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    output_type: Mapped[str] = mapped_column(String(32), default="numeric")
    unit: Mapped[str] = mapped_column(String(64), default="ratio")
    frequency: Mapped[str] = mapped_column(String(32))
    lookback_requirement: Mapped[str] = mapped_column(String(80), default="none")
    computation_method: Mapped[str] = mapped_column(String(160))
    implementation_version: Mapped[str] = mapped_column(String(64))
    required_datasets: Mapped[list[str]] = mapped_column(JSON, default=list)
    required_graph_drivers: Mapped[list[str]] = mapped_column(JSON, default=list)
    temporal_policy: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    missing_data_policy: Mapped[str] = mapped_column(String(80), default="mark_missing")
    normalization_policy: Mapped[str] = mapped_column(String(80), default="none")
    cost_class: Mapped[str] = mapped_column(String(16), default="low")
    determinism: Mapped[str] = mapped_column(String(24), default="deterministic")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class FeatureSet(Base):
    __tablename__ = "feature_sets"
    __table_args__ = (
        UniqueConstraint("workspace_id", "key", "version", name="uq_feature_set_version"),
        CheckConstraint("active_to IS NULL OR active_to > active_from", name="feature_set_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer)
    owner: Mapped[str] = mapped_column(String(120))
    intended_resolution: Mapped[str] = mapped_column(String(24), index=True)
    estimated_compute_cost: Mapped[str] = mapped_column(String(16), default="low")
    active_from: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    active_to: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class FeatureSetMembership(Base):
    __tablename__ = "feature_set_memberships"
    __table_args__ = (
        UniqueConstraint("feature_set_id", "feature_version_id", name="uq_feature_set_member"),
        UniqueConstraint("feature_set_id", "position", name="uq_feature_set_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    feature_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feature_sets.id", ondelete="CASCADE"), index=True
    )
    feature_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feature_definition_versions.id", ondelete="RESTRICT"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)


class FeatureMaterializationJob(Base):
    __tablename__ = "feature_materialization_jobs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "idempotency_key", name="uq_feature_job_workspace_key"),
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled','deferred')",
            name="feature_job_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    feature_set_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("feature_sets.id", ondelete="SET NULL"), index=True
    )
    universe_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_universe_versions.id", ondelete="SET NULL"), index=True
    )
    mode: Mapped[str] = mapped_column(String(24), default="incremental")
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    checkpoint: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    router_override: Mapped[bool] = mapped_column(Boolean, default=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    error_class: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, index=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class FeatureValue(Base):
    __tablename__ = "feature_values"
    __table_args__ = (
        UniqueConstraint(
            "feature_version_id",
            "entity_id",
            "observation_time",
            "input_checksum",
            name="uq_feature_value_input_identity",
        ),
        CheckConstraint(
            "quality_state IN ('complete','partial','missing_inputs','stale_inputs',"
            "'ambiguous_inputs','low_confidence_graph','revised','temporally_unsafe',"
            "'failed_computation')",
            name="feature_value_quality",
        ),
        Index(
            "ix_feature_value_as_of",
            "feature_version_id",
            "entity_id",
            "simulation_eligible_time",
            "observation_time",
        ),
        Index(
            "ix_feature_value_matrix", "entity_id", "simulation_eligible_time", "feature_version_id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    feature_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feature_definition_versions.id", ondelete="RESTRICT"), index=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("economic_entities.id", ondelete="CASCADE"), index=True
    )
    observation_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    effective_time: Mapped[datetime] = mapped_column(UTCDateTime())
    calculation_time: Mapped[datetime] = mapped_column(UTCDateTime())
    simulation_eligible_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    text_value: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(64))
    quality_state: Mapped[str] = mapped_column(String(32), default="complete", index=True)
    quality_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    input_checksum: Mapped[str] = mapped_column(String(64), index=True)
    computation_checksum: Mapped[str] = mapped_column(String(64), index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("feature_materialization_jobs.id", ondelete="SET NULL"), index=True
    )
    deterministic_seed: Mapped[int | None] = mapped_column(Integer)
    normalization: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class FeatureLineage(Base):
    __tablename__ = "feature_lineage"
    __table_args__ = (
        UniqueConstraint(
            "feature_value_id", "lineage_checksum", name="uq_feature_lineage_checksum"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    feature_value_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feature_values.id", ondelete="CASCADE"), index=True
    )
    source_manifest_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_observation_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    graph_relationship_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    grouped_input_manifest: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    computation_version: Mapped[str] = mapped_column(String(64))
    lineage_checksum: Mapped[str] = mapped_column(String(64), index=True)


class ResearchResolutionPolicy(Base):
    __tablename__ = "research_resolution_policies"
    __table_args__ = (
        UniqueConstraint("workspace_id", "version", name="uq_resolution_policy_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[str] = mapped_column(String(40))
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON)
    checksum: Mapped[str] = mapped_column(String(64))
    active_from: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class ResearchBudget(Base):
    __tablename__ = "research_budgets"
    __table_args__ = (
        UniqueConstraint("workspace_id", "policy_id", "level", name="uq_research_budget_level"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_resolution_policies.id", ondelete="CASCADE"), index=True
    )
    level: Mapped[str] = mapped_column(String(24), index=True)
    limits: Mapped[dict[str, Any]] = mapped_column(JSON)
    cost_class: Mapped[str] = mapped_column(String(16))
    monetary_estimate: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))


class ResearchBudgetUsage(Base):
    __tablename__ = "research_budget_usage"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    budget_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_budgets.id", ondelete="CASCADE"), index=True
    )
    screening_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_screening_runs.id", ondelete="CASCADE"), index=True
    )
    usage: Mapped[dict[str, Any]] = mapped_column(JSON)
    decision: Mapped[str] = mapped_column(String(24), index=True)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class FeatureSnapshot(Base):
    __tablename__ = "feature_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    universe_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_universe_versions.id", ondelete="RESTRICT"), index=True
    )
    feature_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feature_sets.id", ondelete="RESTRICT"), index=True
    )
    as_of_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    entity_ids: Mapped[list[str]] = mapped_column(JSON)
    feature_value_ids: Mapped[list[str]] = mapped_column(JSON)
    application_sha: Mapped[str] = mapped_column(String(64))
    migration_head: Mapped[str] = mapped_column(String(40))
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON)
    checksum: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class ResearchScreeningRun(Base):
    __tablename__ = "research_screening_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    universe_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_universe_versions.id", ondelete="RESTRICT"), index=True
    )
    feature_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feature_snapshots.id", ondelete="RESTRICT"), index=True
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_resolution_policies.id", ondelete="RESTRICT"), index=True
    )
    as_of_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    total_candidates: Mapped[int] = mapped_column(Integer)
    promoted: Mapped[int] = mapped_column(Integer, default=0)
    deferred: Mapped[int] = mapped_column(Integer, default=0)
    demoted: Mapped[int] = mapped_column(Integer, default=0)
    rejected: Mapped[int] = mapped_column(Integer, default=0)
    budget_usage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reason_distribution: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    checksum: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class ResearchScreeningDecision(Base):
    __tablename__ = "research_screening_decisions"
    __table_args__ = (
        UniqueConstraint("screening_run_id", "entity_id", name="uq_screening_decision_entity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    screening_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_screening_runs.id", ondelete="CASCADE"), index=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("economic_entities.id", ondelete="CASCADE"), index=True
    )
    score: Mapped[Decimal] = mapped_column(Numeric(12, 8), index=True)
    score_components: Mapped[dict[str, Any]] = mapped_column(JSON)
    recommendation: Mapped[str] = mapped_column(String(24), index=True)
    reason_codes: Mapped[list[str]] = mapped_column(JSON)
    missing_information: Mapped[list[str]] = mapped_column(JSON, default=list)
    budget_impact: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ResearchCandidateState(Base):
    __tablename__ = "research_candidate_states"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "universe_id",
            "entity_id",
            "policy_id",
            name="uq_candidate_policy_state",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    universe_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_universes.id", ondelete="CASCADE"), index=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("economic_entities.id", ondelete="CASCADE"), index=True
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_resolution_policies.id", ondelete="RESTRICT"), index=True
    )
    current_level: Mapped[str] = mapped_column(String(24), index=True)
    previous_level: Mapped[str | None] = mapped_column(String(24))
    entered_at: Mapped[datetime] = mapped_column(UTCDateTime())
    promotion_reason: Mapped[str | None] = mapped_column(Text)
    demotion_reason: Mapped[str | None] = mapped_column(Text)
    supporting_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feature_snapshots.id", ondelete="RESTRICT"), index=True
    )
    budget_impact: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    next_review_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


class ResearchHypothesis(Base):
    __tablename__ = "research_hypotheses"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "subject_entity_id", "title", "version", name="uq_hypothesis_version"
        ),
        CheckConstraint(
            "status IN ('DRAFT','EVIDENCE_REQUIRED','READY_FOR_IMPLEMENTATION','IMPLEMENTED',"
            "'TESTING','REJECTED','PROMISING','VALIDATED','RETIRED')",
            name="hypothesis_status_valid",
        ),
        CheckConstraint("version > 0", name="hypothesis_version_positive"),
        Index("ix_hypothesis_subject_status", "workspace_id", "subject_entity_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    system_owner: Mapped[str] = mapped_column(String(120), default="market-intelligence-lab")
    subject_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("economic_entities.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(240))
    hypothesis_type: Mapped[str] = mapped_column(String(48), index=True)
    economic_rationale: Mapped[str] = mapped_column(Text)
    machine_readable_mechanism: Mapped[dict[str, Any]] = mapped_column(JSON)
    expected_direction: Mapped[str] = mapped_column(String(24))
    expected_horizon: Mapped[str] = mapped_column(String(64))
    required_evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    required_graph_drivers: Mapped[list[str]] = mapped_column(JSON, default=list)
    required_datasets: Mapped[list[str]] = mapped_column(JSON, default=list)
    proposed_outcome: Mapped[dict[str, Any]] = mapped_column(JSON)
    candidate_feature_specification: Mapped[dict[str, Any]] = mapped_column(JSON)
    originating_method: Mapped[str] = mapped_column(String(48), index=True)
    originating_model: Mapped[str | None] = mapped_column(String(160))
    falsification_criteria: Mapped[list[str]] = mapped_column(JSON)
    mechanism_confidence: Mapped[Decimal] = mapped_column(Numeric(7, 6))
    novelty_estimate: Mapped[Decimal] = mapped_column(Numeric(7, 6))
    assumptions: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, index=True)
    simulation_eligible_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    status: Mapped[str] = mapped_column(String(40), default="DRAFT", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    checksum: Mapped[str] = mapped_column(String(64), index=True)


class HypothesisMechanism(Base):
    __tablename__ = "hypothesis_mechanisms"
    __table_args__ = (
        UniqueConstraint("hypothesis_id", "version", name="uq_hypothesis_mechanism_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_hypotheses.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    source_driver: Mapped[str] = mapped_column(String(200))
    affected_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("economic_entities.id", ondelete="CASCADE"), index=True
    )
    relationship_path: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    expected_direction: Mapped[str] = mapped_column(String(24))
    lag_assumptions: Mapped[dict[str, Any]] = mapped_column(JSON)
    intermediate_mechanism: Mapped[str] = mapped_column(Text)
    target_outcome: Mapped[str] = mapped_column(String(160))
    mechanism_confidence: Mapped[Decimal] = mapped_column(Numeric(7, 6))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class HypothesisEvidence(Base):
    __tablename__ = "hypothesis_evidence"
    __table_args__ = (
        CheckConstraint(
            "stance IN ('supporting','contradicting','neutral')", name="hypothesis_evidence_stance"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_hypotheses.id", ondelete="CASCADE"), index=True
    )
    evidence_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence_records.id", ondelete="SET NULL"), index=True
    )
    stance: Mapped[str] = mapped_column(String(24), index=True)
    summary: Mapped[str] = mapped_column(Text)
    source_reference: Mapped[dict[str, Any]] = mapped_column(JSON)
    simulation_eligible_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(7, 6))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class CandidateFeatureSpec(Base):
    __tablename__ = "candidate_feature_specs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "checksum", name="uq_candidate_feature_checksum"),
        CheckConstraint("implementation_version > 0", name="candidate_feature_version_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_hypotheses.id", ondelete="CASCADE"), index=True
    )
    feature_key: Mapped[str] = mapped_column(String(160), index=True)
    required_datasets: Mapped[list[str]] = mapped_column(JSON)
    required_graph_paths: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    transformations: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    aggregation: Mapped[dict[str, Any]] = mapped_column(JSON)
    lookback: Mapped[int] = mapped_column(Integer)
    lag: Mapped[int] = mapped_column(Integer)
    weighting: Mapped[dict[str, Any]] = mapped_column(JSON)
    missing_data_policy: Mapped[str] = mapped_column(String(48))
    normalization: Mapped[str] = mapped_column(String(48))
    expected_direction: Mapped[str] = mapped_column(String(24))
    required_output: Mapped[str] = mapped_column(String(48))
    temporal_policy: Mapped[dict[str, Any]] = mapped_column(JSON)
    implementation_version: Mapped[int] = mapped_column(Integer)
    generator: Mapped[str] = mapped_column(String(120))
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class ResearchOutcomeDefinition(Base):
    __tablename__ = "research_outcome_definitions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "key", "version", name="uq_research_outcome_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(160), index=True)
    outcome_type: Mapped[str] = mapped_column(String(48))
    horizon: Mapped[int] = mapped_column(Integer)
    benchmark: Mapped[str | None] = mapped_column(String(120))
    calculation: Mapped[dict[str, Any]] = mapped_column(JSON)
    temporal_truth_policy: Mapped[dict[str, Any]] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class FactorExperiment(Base):
    __tablename__ = "factor_experiments"
    __table_args__ = (
        UniqueConstraint("workspace_id", "checksum", name="uq_factor_experiment_checksum"),
        CheckConstraint(
            "status IN ('DRAFT','SCHEDULED','RUNNING','COMPLETED','FAILED','REJECTED')",
            name="factor_experiment_status",
        ),
        Index("ix_factor_experiment_hypothesis_status", "hypothesis_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_hypotheses.id", ondelete="RESTRICT"), index=True
    )
    candidate_feature_spec_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_feature_specs.id", ondelete="RESTRICT"), index=True
    )
    universe_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_universe_versions.id", ondelete="RESTRICT"), index=True
    )
    feature_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feature_snapshots.id", ondelete="RESTRICT"), index=True
    )
    outcome_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_outcome_definitions.id", ondelete="RESTRICT"), index=True
    )
    graph_state: Mapped[dict[str, Any]] = mapped_column(JSON)
    period_start: Mapped[datetime] = mapped_column(UTCDateTime())
    period_end: Mapped[datetime] = mapped_column(UTCDateTime())
    validation_protocol: Mapped[dict[str, Any]] = mapped_column(JSON)
    cost_assumptions: Mapped[dict[str, Any]] = mapped_column(JSON)
    application_sha: Mapped[str] = mapped_column(String(64))
    dependency_versions: Mapped[dict[str, str]] = mapped_column(JSON)
    seed: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="DRAFT", index=True)
    conclusion: Mapped[str | None] = mapped_column(String(40), index=True)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class FactorExperimentFold(Base):
    __tablename__ = "factor_experiment_folds"
    __table_args__ = (
        UniqueConstraint("experiment_id", "fold_number", name="uq_factor_experiment_fold"),
        CheckConstraint("fold_number >= 0", name="factor_fold_number_nonnegative"),
        Index("ix_factor_fold_experiment_ranges", "experiment_id", "test_start", "test_end"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("factor_experiments.id", ondelete="CASCADE"), index=True
    )
    fold_number: Mapped[int] = mapped_column(Integer)
    train_start: Mapped[datetime] = mapped_column(UTCDateTime())
    train_end: Mapped[datetime] = mapped_column(UTCDateTime())
    validation_start: Mapped[datetime] = mapped_column(UTCDateTime())
    validation_end: Mapped[datetime] = mapped_column(UTCDateTime())
    test_start: Mapped[datetime] = mapped_column(UTCDateTime())
    test_end: Mapped[datetime] = mapped_column(UTCDateTime())
    purge_observations: Mapped[int] = mapped_column(Integer, default=0)
    embargo_observations: Mapped[int] = mapped_column(Integer, default=0)
    observations: Mapped[int] = mapped_column(Integer)
    coverage: Mapped[Decimal] = mapped_column(Numeric(7, 6))
    factor_statistics: Mapped[dict[str, Any]] = mapped_column(JSON)
    model_statistics: Mapped[dict[str, Any]] = mapped_column(JSON)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    failures: Mapped[list[str]] = mapped_column(JSON, default=list)


class FactorStatistic(Base):
    __tablename__ = "factor_statistics"
    __table_args__ = (
        UniqueConstraint(
            "experiment_id", "fold_id", "metric_key", "segment", name="uq_factor_statistic_key"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("factor_experiments.id", ondelete="CASCADE"), index=True
    )
    fold_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("factor_experiment_folds.id", ondelete="CASCADE"), index=True
    )
    metric_key: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    segment: Mapped[str] = mapped_column(String(120), default="overall")
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class MultipleTestingResult(Base):
    __tablename__ = "multiple_testing_results"
    __table_args__ = (
        CheckConstraint(
            "correction_method IN ('bonferroni','holm','benjamini-hochberg')",
            name="multiple_testing_method",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("factor_experiments.id", ondelete="CASCADE"), index=True
    )
    hypothesis_family: Mapped[str] = mapped_column(String(160), index=True)
    number_of_hypotheses: Mapped[int] = mapped_column(Integer)
    raw_p_value: Mapped[Decimal] = mapped_column(Numeric(18, 16))
    adjusted_p_value: Mapped[Decimal] = mapped_column(Numeric(18, 16))
    correction_method: Mapped[str] = mapped_column(String(32))
    rejected_null: Mapped[bool] = mapped_column(Boolean)


class RobustnessResult(Base):
    __tablename__ = "robustness_results"
    __table_args__ = (
        UniqueConstraint("experiment_id", "variant_checksum", name="uq_robustness_variant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("factor_experiments.id", ondelete="CASCADE"), index=True
    )
    variant_type: Mapped[str] = mapped_column(String(64), index=True)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON)
    statistics: Mapped[dict[str, Any]] = mapped_column(JSON)
    passed: Mapped[bool] = mapped_column(Boolean, index=True)
    variant_checksum: Mapped[str] = mapped_column(String(64))


class AblationResult(Base):
    __tablename__ = "ablation_results"
    __table_args__ = (
        UniqueConstraint("experiment_id", "component_key", name="uq_ablation_component"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("factor_experiments.id", ondelete="CASCADE"), index=True
    )
    component_key: Mapped[str] = mapped_column(String(120))
    included_components: Mapped[list[str]] = mapped_column(JSON)
    statistics: Mapped[dict[str, Any]] = mapped_column(JSON)
    contribution: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))


class NegativeControlResult(Base):
    __tablename__ = "negative_control_results"
    __table_args__ = (
        CheckConstraint(
            "control_type IN ('shuffled','deterministic_noise','unrelated_sector',"
            "'temporal_corruption')",
            name="negative_control_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("factor_experiments.id", ondelete="CASCADE"), index=True
    )
    control_type: Mapped[str] = mapped_column(String(40), index=True)
    statistics: Mapped[dict[str, Any]] = mapped_column(JSON)
    persistent_power_detected: Mapped[bool] = mapped_column(Boolean)
    methodology_valid: Mapped[bool] = mapped_column(Boolean)
    failure_reason: Mapped[str | None] = mapped_column(Text)


class ResearchPromotionEvent(Base):
    __tablename__ = "research_promotion_events"
    __table_args__ = (
        CheckConstraint(
            "to_stage IN ('DRAFT','EVIDENCE_CHECKED','IMPLEMENTED','LEAKAGE_CHECKED',"
            "'BACKTESTED','WALK_FORWARD_PASSED','ROBUSTNESS_PASSED','OOS_PASSED',"
            "'PAPER_ELIGIBLE','REJECTED')",
            name="research_promotion_stage",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_hypotheses.id", ondelete="CASCADE"), index=True
    )
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("factor_experiments.id", ondelete="SET NULL"), index=True
    )
    from_stage: Mapped[str | None] = mapped_column(String(40))
    to_stage: Mapped[str] = mapped_column(String(40), index=True)
    gate_version: Mapped[str] = mapped_column(String(40))
    decision: Mapped[str] = mapped_column(String(24))
    reasons: Mapped[list[str]] = mapped_column(JSON)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, index=True)


class ExperimentManifest(Base):
    __tablename__ = "experiment_manifests"
    __table_args__ = (UniqueConstraint("experiment_id", name="uq_experiment_manifest_experiment"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("factor_experiments.id", ondelete="CASCADE"), index=True
    )
    hypothesis_version: Mapped[int] = mapped_column(Integer)
    feature_spec: Mapped[dict[str, Any]] = mapped_column(JSON)
    feature_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feature_snapshots.id", ondelete="RESTRICT"), index=True
    )
    universe_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_universe_versions.id", ondelete="RESTRICT"), index=True
    )
    graph_reference_state: Mapped[dict[str, Any]] = mapped_column(JSON)
    source_manifests: Mapped[list[str]] = mapped_column(JSON)
    software_sha: Mapped[str] = mapped_column(String(64))
    alembic_revision: Mapped[str] = mapped_column(String(40))
    dependency_versions: Mapped[dict[str, str]] = mapped_column(JSON)
    model_config: Mapped[dict[str, Any]] = mapped_column(JSON)
    validation_protocol: Mapped[dict[str, Any]] = mapped_column(JSON)
    random_seed: Mapped[int] = mapped_column(Integer)
    time_boundaries: Mapped[dict[str, Any]] = mapped_column(JSON)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    checksum: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class ExternalResearchEngineRun(Base):
    __tablename__ = "external_research_engine_runs"
    __table_args__ = (
        CheckConstraint("engine IN ('qlib','rd-agent')", name="external_research_engine"),
        CheckConstraint(
            "status IN ('unavailable','disabled','queued','running','completed','failed')",
            name="engine_run_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("factor_experiments.id", ondelete="SET NULL"), index=True
    )
    engine: Mapped[str] = mapped_column(String(24), index=True)
    engine_version: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), index=True)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON)
    seed: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    input_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("feature_snapshots.id", ondelete="SET NULL"), index=True
    )
    artifacts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    output_checksum: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, index=True)
