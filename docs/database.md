# Database

## Models

- `Asset`: normalized symbol and descriptive stock/ETF metadata.
- `PriceBar`: OHLCV observation plus source and four time semantics.
- `DataSource`: provider identity, health, licensing notes, and last success.
- `DataIngestionRun`: status, timing, record count, and safe error summary for a provider run.
- `Watchlist`: named user-curated collection.
- `WatchlistAsset`: many-to-many link with an added timestamp.
- `AuditEvent`: append-only application mutation record.
- `Strategy` / `StrategyVersion`: named strategy identity and immutable validated parameter versions.
- `BacktestRun`, `BacktestTrade`, `BacktestDailySnapshot`: reproducible simulation inputs, executions, metrics, and daily state.
- `Signal` / `SignalFactor`: explainable signal direction, timing, source bar, and indicator factors.
- `PaperPortfolio`, `PaperPosition`, `PaperOrder`, `PaperFill`, `PortfolioSnapshot`: simulated cash, holdings, order lifecycle, execution, and performance history.
- `RiskRule`: enabled portfolio-level pre-trade limits and configuration.

UUID primary keys avoid coupling identifiers to database insertion order and support future distributed ingestion. Symbols and watchlist names are unique. A price bar is unique across asset, interval, event time, and data source.

## Cascades and restrictions

Deleting an asset removes its price bars and watchlist links. Deleting a watchlist removes only its links. Deleting a referenced data source is restricted so provenance cannot silently disappear. SQLite foreign keys are explicitly enabled on every connection.

## Numeric and time behavior

Prices use `NUMERIC(18, 6)` and are serialized as decimals. Volume is a nonnegative integer. All timestamps are aware UTC in application code. SQLite stores timestamps without full timezone semantics, so `UTCDateTime` normalizes writes and restores UTC awareness on reads. PostgreSQL can preserve `TIMESTAMP WITH TIME ZONE` behavior natively.

## Migrations

Revisions `0001_foundation` and `0002_backtesting_paper_trading` are authoritative. Never edit a migration that has shipped; add a new revision. Verify from an empty database with `alembic upgrade head`, then use `alembic check` to detect ORM/schema drift.
