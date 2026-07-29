# Testing

## Backend

Pytest uses an isolated SQLite database per test. Coverage includes the foundation workflows plus indicator calculations, seven strategy contracts, strict parameter validation, shared-cash and delayed no-lookahead backtests, costs and exposure controls, metrics and provenance, paper market/limit/stop/stop-limit behavior, idempotency, long-only enforcement, fills, P&L, pause/resume, risk rejections, provider registration, durable imports, retries/restarts, provenance, quality validation, corporate actions, exchange calendars, and API validation.

Run `pytest`, `ruff check .`, and `mypy apps packages scripts` from the root. CI also applies Alembic to an empty database and runs `alembic check`.

## Frontend

Vitest and React Testing Library cover the foundation screens, backtesting and paper-trading workflows, provider health, import creation/detail, data quality, corporate actions, and exchange sessions. Run `pnpm test`, `pnpm run typecheck`, and `pnpm run build` from `apps/web`.

## Browser workflow

The Playwright smoke test loads the application, finds a seeded asset, creates a watchlist, adds AAPL, opens its detail page, and fails on browser-console errors. Install Chromium once with `pnpm exec playwright install chromium`, then run `pnpm run test:e2e`.

Tests must not be reported as passed unless they ran. Docker verification is distinct from source-level verification and is reported separately when Docker is unavailable.
