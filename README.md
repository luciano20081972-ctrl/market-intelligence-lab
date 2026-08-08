# Market Intelligence Lab

Market Intelligence Lab is a workspace-isolated stock and ETF research workbench for historical data, explainable signals, reproducible backtests, simulated paper trading, SEC filing intelligence, portfolio analytics, and constrained optimization. Version 0.6.0 adds governed, replaceable upstream adapters without adding brokerage or real-money execution.

The v0.6 application schema is at Alembic revision `6b8d9e0f1a2b`. The v0.5.1 Supabase
Auth/JWKS and deny-by-default PostgREST behavior were live-verified with
temporary users that were removed after the rehearsal. Direct
FastAPI-to-staging PostgreSQL runtime connectivity remains unverified because
the workstation's session-pooler authentication is unresolved.

> **Research data and simulated trading only.** Bundled prices are synthetic. External Stooq history is read-only, is not bundled, may be delayed or incomplete, and requires an independent terms/licensing review before production or redistribution use.

## Safety scope

This release has no Fidelity or brokerage integration, brokerage login automation, credential storage, real-money execution, order submission, options, margin, short selling, withdrawals, or autonomous AI trading. It makes no claim of guaranteed or optimal profit.

## Architecture overview

- `apps/api`: FastAPI HTTP application and `/api/v1` routes.
- `apps/web`: React, TypeScript, Vite, TanStack Query, React Router, and Recharts client.
- `packages/database`: SQLAlchemy 2 models, UTC-aware types, and transaction helpers.
- `packages/auth` and `packages/security`: provider-neutral identity, Supabase JWT verification, workspace roles, and tenant query/write guards.
- `packages/market_data`: Stooq, Twelve Data, and synthetic adapters, durable jobs and leases, worker/schedules, calendars, comparison, validation, and observability.
- `packages/provenance`: append-only application audit events.
- `packages/strategies`: seven versioned, parameter-validated transparent strategies and technical indicators.
- `packages/backtesting`: shared-cash, long-only, no-lookahead simulation and performance metrics.
- `packages/paper_trading`: deterministic market/limit/stop/stop-limit simulation and portfolio risk rules.
- `packages/sec_intelligence`: normalized, fixture-first EdgarTools boundary and SEC provenance.
- `packages/analytics` and `packages/optimization`: QuantStats reconciliation and skfolio-compatible constrained experiments.
- `packages/upstream` and `packages/external_engines`: license governance, stable protocols, and disabled-by-default LEAN prototype.
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
# Optional, pinned research adapters:
pip install -e ".[integrations]"
```

On macOS/Linux, activate with `source .venv/bin/activate`.

Install the frontend:

```powershell
Set-Location apps/web
pnpm install
Set-Location ../..
```

## Environment setup

Copy `.env.example` to `.env` and adjust only local, non-secret values. `.env` is ignored by Git. The application reads variables prefixed with `MIL_`; the browser reads `VITE_` configuration at build time. `MIL_AUTH_MODE=disabled` is local/test only and production refuses it. Supabase mode requires its URL/audience and the browser's public publishable key. Twelve Data uses backend-only `MIL_TWELVE_DATA_API_KEY`. Never expose a Supabase service-role key or provider key to the browser.

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
pytest --cov=apps --cov=packages --cov-report=term-missing --cov-report=xml
python scripts/verify.py
python scripts/validate_supabase_staging.py  # opt-in staging configuration only
python scripts/validate_upstream.py
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
- SEC ordinary workflows use deterministic fixtures. The bounded live worker transport is opt-in and was not run for this release.
- Backtests use fixed daily demonstration bars; intraday execution, partial fills, market impact, and liquidity depth are not modeled.
- Supabase Auth and the v0.5.1 staging schema/lockdown were live-verified; direct FastAPI-to-staging PostgreSQL pooler connectivity remains unverified, and application-managed immediate session revocation is limited by provider support.
- Application-layer workspace isolation is implemented and tested. PostgreSQL RLS is enabled as deny-by-default defense in depth with no browser-facing policies; complete workspace-aware database policies are not claimed.
- PostgreSQL verification runs in CI and is skipped locally unless `MIL_POSTGRES_TEST_DATABASE_URL` points to a disposable database.
- Twelve Data is fixture-tested only; no live request was run, and no commercial redistribution right is claimed.
- Distributed/multi-host rate limiting and worker coordination remain deferred; the current limiter and worker target one application instance.
- QuantStats, skfolio, and EdgarTools are optional pinned dependencies. Compatibility fixtures keep core functionality available when they are absent.
- LEAN process/container execution is not enabled; v0.6 provides only detection, normalized contracts, and a deterministic result-package prototype.

See [the roadmap](docs/roadmap.md) for the planned next increment.

## Financial-risk disclaimer

Market Intelligence Lab is research software, not financial advice. Synthetic prices and simulated results do not represent actual execution and do not predict future performance. Investing can result in loss of principal. Independently verify all information before making financial decisions.

## Further documentation

- [Architecture](docs/architecture.md)
- [Database](docs/database.md)
- [Data provenance](docs/data-provenance.md)
- [SEC intelligence](docs/sec-intelligence.md)
- [Upstream governance](docs/upstream/README.md)
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

## Real market-data operations (v0.5.0)

Stooq retains its strict fixed-host CSV adapter and honest degraded/unknown status. Twelve Data is the second documented adapter: it uses a fixed HTTPS host, header credential, bounded daily JSON requests, response limits, normalized errors, checksums, and strict OHLCV validation. It is disabled without its environment key and fixture-tested rather than live-verified. Synthetic data remains enabled for offline tests. No provider redistribution right is claimed.

The v0.4.1 diagnostic distinguishes healthy compatible CSV, reachable-but-invalid responses, no data, rate/access responses, and network unavailability without storing or displaying a remote response body. A live diagnostic on 2026-07-29 reached `stooq.com` over HTTPS with HTTP 200 but returned `text/html` verification content, so that environment was correctly classified `html_access_page`, not healthy. External imports remain disabled until the exact request passes preview validation.

Imports are queued by default and support full/incremental modes, idempotency keys, exponential retry state, cancellation, resumable cursors, leases, heartbeat renewal, abandoned-job recovery, dead-letter outcomes, schedules, provenance-complete bars, and conflict preservation. Run `python -m packages.market_data.worker` for continuous processing or add `--once` for one attempt.

XNYS sessions come from the maintained `exchange-calendars` package and are persisted for 2020–2035 by the standard seed. See the real-market-data, worker, scheduling, observability, reconciliation, and rate-limiting guides in `docs/`.

See the provider framework, data ingestion, data quality, corporate actions, and exchange calendar guides in docs/.
