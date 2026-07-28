# Changelog

All notable changes follow Keep a Changelog conventions. The project uses semantic versioning.

## [0.2.0] - 2026-07-28

### Added

- Seven versioned transparent strategies and deterministic SMA, EMA, RSI, MACD, ATR, return, volatility, volume, relative-strength, and drawdown indicators.
- Shared-cash, long-only, point-in-time backtests with delayed execution, transaction-cost assumptions, benchmark comparison, provenance, risk sizing, trades, signals, and daily snapshots.
- Simulated portfolios with idempotent market, limit, stop, and stop-limit orders; fills, positions, P&L, performance snapshots, pause/resume, and nine configurable pre-trade risk rules.
- Versioned strategy, backtest, paper-portfolio, order, fill, position, performance, and risk-rule APIs.
- Strategy Lab, backtest reports, paper portfolio dashboard, simulated order ticket, and risk settings interface.
- Alembic revision `0002_backtesting_paper_trading`, backend behavioral coverage, and Sprint 2 frontend workflow tests.

### Safety

- All results and orders are explicitly hypothetical. No brokerage connectivity, credentials, margin, options, short selling, force execution, or real-money capability was added.

## [0.1.0] - 2026-07-28

### Added

- FastAPI and SQLAlchemy foundation with versioned system, asset, price, and watchlist APIs.
- Alembic foundation migration and portable SQLite/PostgreSQL-oriented schema.
- Deterministic nine-asset dataset with 1,080 source-labeled daily bars.
- Responsive React research interface with overview, watchlists, asset explorer/detail, sources, status, and documentation.
- Provenance timestamps, ingestion runs, audit events, UTC enforcement, transactional mutations, and database constraints.
- Backend, frontend, and Playwright tests; Ruff, MyPy, Vitest, build, migration, and CI checks.
- Cross-platform development launcher, Docker images, Compose topology, and security/operations documentation.
