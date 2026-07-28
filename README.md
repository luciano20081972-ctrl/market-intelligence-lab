# Market Intelligence Lab

Market Intelligence Lab is a local-first stock and ETF research foundation for historical data, explainable signals, reproducible backtests, political-market intelligence, and simulated paper trading. Version 0.1.0 establishes a working data model, deterministic demonstration dataset, versioned API, and responsive research interface.

> **Synthetic demonstration data — not live market data.** The bundled prices are generated locally from a fixed seed and must never be interpreted as real, current, or licensed market information.

## Safety scope

This release has no Fidelity or brokerage integration, brokerage login automation, credential storage, real-money execution, order submission, options, margin, short selling, withdrawals, or autonomous AI trading. It makes no claim of guaranteed or optimal profit.

## Architecture overview

- `apps/api`: FastAPI HTTP application and `/api/v1` routes.
- `apps/web`: React, TypeScript, Vite, TanStack Query, React Router, and Recharts client.
- `packages/database`: SQLAlchemy 2 models, UTC-aware types, and transaction helpers.
- `packages/market_data`: provider protocol and deterministic demonstration seed.
- `packages/provenance`: append-only application audit events.
- `packages/strategies`, `backtesting`, `paper_trading`, `risk`: small domain contracts that preserve simulation boundaries.
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

## Local startup

Start both services with migrations and configured seeding:

```powershell
python scripts/dev.py --seed
```

Open `http://127.0.0.1:5173`; API documentation is at `http://127.0.0.1:8000/docs`. Press Ctrl+C to stop both processes.

Separate startup commands:

```powershell
python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload
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

- Data is synthetic and fixed; there is no live or delayed market feed.
- No SEC, macroeconomic, congressional-disclosure, political-event, or regulatory-event ingestion yet.
- Strategy, backtesting, paper-trading, and risk packages expose safe foundations only; they do not yet run portfolios.
- Authentication and multi-user isolation are not implemented.
- SQLite is tested locally; PostgreSQL deployment testing is deferred.
- Market calendars, splits, dividends, and corporate-action adjustment are not modeled in v0.1.0.

See [the roadmap](docs/roadmap.md) for the planned next increment.

## Financial-risk disclaimer

Market Intelligence Lab is research software, not financial advice. Synthetic prices and simulated results do not represent actual execution and do not predict future performance. Investing can result in loss of principal. Independently verify all information before making financial decisions.

## Further documentation

- [Architecture](docs/architecture.md)
- [Database](docs/database.md)
- [Data provenance](docs/data-provenance.md)
- [Local development](docs/local-development.md)
- [Testing](docs/testing.md)
- [Security](SECURITY.md)
- [Roadmap](docs/roadmap.md)
- [Troubleshooting](docs/troubleshooting.md)
