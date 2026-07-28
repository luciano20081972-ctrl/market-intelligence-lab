# Local development

## Standard workflow

1. Install Python 3.12+, Node.js 22+, pnpm 11 (or npm), and Git.
2. Create `.venv`, then run `pip install -e ".[dev]"`.
3. Run `pnpm install` inside `apps/web`.
4. Copy `.env.example` to `.env` if configuration changes are needed.
5. Run `python scripts/dev.py --seed` from the repository root.

The launcher uses npm when available and otherwise pnpm. It refuses to start when no supported package manager or installed frontend dependencies are available, and it never installs packages implicitly.

## Configuration

Settings are prefixed with `MIL_`. Use an absolute or root-relative SQLite URL locally. PostgreSQL URLs are supported by the schema design but require the optional `postgres` dependency. CORS origins are a JSON list. `MIL_SEED_DEMO_DATA` controls launcher/container seeding.

The browser uses `VITE_API_BASE_URL`. Vite variables are public at build time; never place secrets in a `VITE_` variable.

## Working without the launcher

Apply migrations and seed once, run Uvicorn from the repository root, then run `pnpm run dev` from `apps/web`. Stop each process with Ctrl+C.

Runtime databases, logs, caches, test output, build output, and `.env` remain untracked by design.
