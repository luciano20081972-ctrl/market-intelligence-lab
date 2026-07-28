# Troubleshooting

## `python scripts/dev.py` says the package manager is missing

Install a current Node.js LTS release with pnpm or npm and reopen the terminal. Then run `pnpm install` in `apps/web`.

## The API reports `no such table`

From the repository root, activate the intended virtual environment and run `alembic upgrade head`. Confirm `MIL_DATABASE_URL` points to the same database used by Uvicorn.

## Seed produces zero inserted records

That is expected after a successful seed. The seed is idempotent. Verify `/api/v1/system/info` reports nine assets and 1,080 demonstration bars.

## Browser requests fail or CORS appears in the console

Confirm the API is reachable at the URL in `VITE_API_BASE_URL` and that the exact frontend origin is present in `MIL_CORS_ORIGINS`. JSON-list syntax is required.

## SQLite database is locked

Stop duplicate development servers and database viewers, then retry. Do not use SQLite for a write-heavy multi-user deployment; use PostgreSQL in a later deployment sprint.

## Alembic reports schema drift

Do not edit the database manually. Review ORM changes, generate a new migration, inspect it carefully, and re-run both a clean upgrade and `alembic check`.

## Docker web loads but API calls fail

Use the Compose web URL on port 8080. Its nginx server proxies `/api` and `/health` to the API service. Inspect `docker compose ps` and `docker compose logs api` without pasting secrets into issue reports.
