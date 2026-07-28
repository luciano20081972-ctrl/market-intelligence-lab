# Testing

## Backend

Pytest uses an isolated SQLite database per test. Coverage includes health and public system information; clean migration; seed determinism/idempotency; asset lookup, normalization, search, sorting, and pagination; price provenance and uniqueness; UTC behavior; watchlist CRUD and membership conflicts; invalid inputs; cascades; audit creation; and secret redaction.

Run `pytest`, `ruff check .`, and `mypy apps packages scripts` from the root. CI also applies Alembic to an empty database and runs `alembic check`.

## Frontend

Vitest and React Testing Library cover navigation/application rendering, loading, API error, empty results, watchlist creation, adding an asset, asset detail/provenance, and the demonstration warning. Run `pnpm test`, `pnpm run typecheck`, and `pnpm run build` from `apps/web`.

## Browser workflow

The Playwright smoke test loads the application, finds a seeded asset, creates a watchlist, adds AAPL, opens its detail page, and fails on browser-console errors. Install Chromium once with `pnpm exec playwright install chromium`, then run `pnpm run test:e2e`.

Tests must not be reported as passed unless they ran. Docker verification is distinct from source-level verification and is reported separately when Docker is unavailable.
