# Market Intelligence Lab

Market Intelligence Lab is a local-first stock and ETF research workbench for historical data, explainable signals, reproducible backtests, and simulated paper trading. Version 0.4.1 stabilizes the read-only Stooq integration with strict response classification, safe provider diagnostics, deterministic fixture-backed imports, and external-import preflight protection while retaining the v0.4.0 durable worker, scheduling, reconciliation, and synthetic demonstrations.

> **Research data and simulated trading only.** Bundled prices are synthetic. External Stooq history is read-only, is not bundled, may be delayed or incomplete, and requires an independent terms/licensing review before production or redistribution use.

## Safety scope

This release has no Fidelity or brokerage integration, brokerage login automation, credential storage, real-money execution, order submission, options, margin, short selling, withdrawals, or autonomous AI trading. It makes no claim of guaranteed or optimal profit.

## Architecture overview

- `apps/api`: FastAPI HTTP application and `/api/v1` routes.
- `apps/web`: React, TypeScript, Vite, TanStack Query, React Router, and Recharts client.
- `packages/database`: SQLAlchemy 2 models, UTC-aware types, and transaction helpers.
- `packages/market_data`: operational Stooq and synthetic adapters, durable jobs and leases, worker/schedules, maintained exchange calendars, reconciliation, validation, and observability.
- `packages/provenance`: append-only application audit events.
- `packages/strategies`: seven versioned, parameter-validated transparent strategies and technical indicators.
- `packages/backtesting`: shared-cash, long-only, no-lookahead simulation and performance metrics.
- `packages/paper_trading`: deterministic market/limit/stop/stop-limit simulation and portfolio risk rules.
- `migrations`: authoritative Alembic schema history.

SQLite is the default local database. UUID keys, explicit constraints, portable column types, and SQLAlchemy abstractions keep the schema PostgreSQL-compatible.

## Prerequisites

- Python 3.12 or newer
- Node.js 22 with pnpm 11 (recommended) or npm 10+
- Git
- Docker Desktop (optional)

## Installation

Create and activate a virtual environment, then install the backend:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

On macOS/Linux, activate with `source .venv/bin/activate`.

Install the frontend:

```powershell
Set-Location apps/web
pnpm install
Set-Location ../..
```

## Environment setup

Copy `.env.example` to `.env` and adjust only local, non-secret values. `.env` is ignored by Git. The application reads variables prefixed with `MIL_`; the browser reads `VITE_API_BASE_URL` at build time. Never put brokerage or production credentials in either file.

```powershell
Copy-Item .env.example .env
```

## Database migration and seeding

```powershell
alembic upgrade head
python scripts/seed.py
```

Seeding is deterministic and idempotent. It creates nine assets and 120 daily bars per asset. Re-running it does not duplicate records.

## Research workflows

Open **Strategy Lab** to inspect the seven built-in rules and run a backtest. Results include trades, equity, drawdown, benchmark comparison, exact data-source identifiers, strategy configuration, and execution assumptions. Signals become eligible only on a later aligned bar after their publication/effective time; all assets share one cash balance.

Open **Paper Portfolios** to create a hypothetical cash account. Preview each simulated order before submission to see its deterministic stored-bar outcome and all risk rejections. Market, limit, stop, and stop-limit orders are supported; client order IDs make retries idempotent. Limit prices are never violated, short selling is disabled, and no request is sent to a broker.

See [Backtesting and paper trading](docs/backtesting-paper-trading.md) for calculation, fill, gap, and risk-control details.

## Local startup

Start both services with migrations and configured seeding:

```powershell
python scripts/dev.py --seed
```

Open `http://127.0.0.1:5173`; API documentation is at `http://127.0.0.1:8000/docs`. Press Ctrl+C to stop both processes.

Start the stack with the explicit durable worker when processing queued imports:

```powershell
python scripts/dev.py --seed --worker
```

Separate startup commands:

```powershell
python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload
python -m packages.market_data.worker
```

```powershell
Set-Location apps/web
pnpm run dev
```

## Tests and quality checks

```powershell
ruff check .
mypy apps packages scripts
pytest
python scripts/verify.py
```

```powershell
Set-Location apps/web
pnpm run typecheck
pnpm test
pnpm run build
pnpm exec playwright install chromium
pnpm run test:e2e
```

Migration verification:

```powershell
$env:MIL_DATABASE_URL="sqlite:///./migration-check.db"
alembic upgrade head
alembic check
Remove-Item migration-check.db
```

## Docker

```powershell
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/health
docker compose down
```

The frontend is served at `http://127.0.0.1:8080`. Runtime database data lives in a named Docker volume and is not committed.

## Current limitations

- Stooq integration is historical daily OHLCV only; it is not a real-time feed and provides no SLA.
- Stooq may return a reachable HTML verification/access page instead of CSV; v0.4.1 reports that state as degraded and blocks the external import rather than accepting or exposing the body.
- No SEC, macroeconomic, congressional-disclosure, political-event, or regulatory-event ingestion yet.
- Backtests use fixed daily demonstration bars; intraday execution, partial fills, market impact, and liquidity depth are not modeled.
- Authentication and multi-user isolation are not implemented.
- SQLite is tested locally; PostgreSQL deployment testing is deferred.
- Authentication and distributed/multi-host worker coordination are deferred; the current rate limiter and worker target a single application instance.

See [the roadmap](docs/roadmap.md) for the planned next increment.

## Financial-risk disclaimer

Market Intelligence Lab is research software, not financial advice. Synthetic prices and simulated results do not represent actual execution and do not predict future performance. Investing can result in loss of principal. Independently verify all information before making financial decisions.

## Further documentation

- [Architecture](docs/architecture.md)
- [Database](docs/database.md)
- [Data provenance](docs/data-provenance.md)
- [Backtesting and paper trading](docs/backtesting-paper-trading.md)
- [Backtesting methodology](docs/backtesting-methodology.md)
- [Order execution model](docs/order-execution-model.md)
- [Paper trading](docs/paper-trading.md)
- [Risk controls](docs/risk-controls.md)
- [Local development](docs/local-development.md)
- [Testing](docs/testing.md)
- [Security](SECURITY.md)
- [Roadmap](docs/roadmap.md)
- [Troubleshooting](docs/troubleshooting.md)

## Real market-data operations (v0.4.1)

Stooq is enabled as the first operational external adapter because its fixed HTTPS endpoint requires no API key and can provide bounded daily OHLCV requests. The adapter never accepts user-controlled URLs, follows no redirects, limits response size, maps simple U.S. stock/ETF symbols such as `AAPL`, `MSFT`, and `SPY` to the `.us` suffix, and accepts only UTF-8/ASCII-compatible comma-delimited data with the canonical `Date,Open,High,Low,Close,Volume` fields. BOMs, header capitalization, surrounding header whitespace, and CRLF/LF are normalized; HTML, plaintext errors, unsupported delimiters, unknown/duplicate schemas, missing values, invalid dates/numbers/OHLC, and negative volume are rejected. No claim of commercial redistribution rights is made. Other external providers remain disabled placeholders; synthetic data remains enabled for offline tests.

The v0.4.1 diagnostic distinguishes healthy compatible CSV, reachable-but-invalid responses, no data, rate/access responses, and network unavailability without storing or displaying a remote response body. A live diagnostic on 2026-07-29 reached `stooq.com` over HTTPS with HTTP 200 but returned `text/html` verification content, so that environment was correctly classified `html_access_page`, not healthy. External imports remain disabled until the exact request passes preview validation.

Imports are queued by default and support full/incremental modes, idempotency keys, exponential retry state, cancellation, resumable cursors, leases, heartbeat renewal, abandoned-job recovery, dead-letter outcomes, schedules, provenance-complete bars, and conflict preservation. Run `python -m packages.market_data.worker` for continuous processing or add `--once` for one attempt.

XNYS sessions come from the maintained `exchange-calendars` package and are persisted for 2020–2035 by the standard seed. See the real-market-data, worker, scheduling, observability, reconciliation, and rate-limiting guides in `docs/`.

See the provider framework, data ingestion, data quality, corporate actions, and exchange calendar guides in docs/.
