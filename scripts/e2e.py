"""Launch the canonical isolated Playwright stack."""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web"
API_PORT = 8012
WEB_PORT = 5182


def main() -> int:
    package_manager = shutil.which("pnpm.cmd" if sys.platform == "win32" else "pnpm")
    if package_manager is None:
        raise RuntimeError("pnpm is required for the Playwright stack")
    with tempfile.TemporaryDirectory(prefix="mil-e2e-") as temporary:
        database = Path(temporary) / "playwright.db"
        environment = os.environ.copy()
        environment.update(
            {
                "MIL_DATABASE_URL": f"sqlite:///{database.as_posix()}",
                "MIL_AUTH_MODE": "disabled",
                "MIL_ENVIRONMENT": "development",
                "MIL_API_PORT": str(API_PORT),
                "MIL_WEB_PORT": str(WEB_PORT),
                "MIL_CORS_ORIGINS": f'["http://127.0.0.1:{WEB_PORT}"]',
                "VITE_API_BASE_URL": f"http://127.0.0.1:{API_PORT}",
            }
        )
        environment.pop("VITE_SUPABASE_URL", None)
        environment.pop("VITE_SUPABASE_PUBLISHABLE_KEY", None)
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT,
            env=environment,
            check=True,
        )
        subprocess.run([sys.executable, "scripts/seed.py"], cwd=ROOT, env=environment, check=True)
        with sqlite3.connect(database) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=30000")
        api_command = [
            sys.executable,
            "-m",
            "uvicorn",
            "apps.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(API_PORT),
        ]
        web_command = [
            package_manager,
            "--dir",
            str(WEB),
            "exec",
            "vite",
            "--host",
            "127.0.0.1",
            "--port",
            str(WEB_PORT),
        ]
        processes = [subprocess.Popen(api_command, cwd=ROOT, env=environment)]
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if any(process.poll() is not None for process in processes):
                    raise RuntimeError("API or worker exited before E2E readiness")
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{API_PORT}/health/ready", timeout=1
                    ) as response:
                        if response.status == 200:
                            break
                except (urllib.error.URLError, TimeoutError):
                    time.sleep(0.1)
            else:
                raise RuntimeError("API did not become ready for Playwright")
            processes.append(
                subprocess.Popen(
                    [sys.executable, "-m", "packages.market_data.worker"],
                    cwd=ROOT,
                    env=environment,
                )
            )
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if processes[1].poll() is not None:
                    raise RuntimeError("worker exited before E2E readiness")
                with sqlite3.connect(database) as connection:
                    ready = connection.execute(
                        "SELECT 1 FROM worker_instances WHERE status IN ('idle', 'busy') LIMIT 1"
                    ).fetchone()
                if ready is not None:
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError("worker did not become ready for Playwright")
            processes.append(subprocess.Popen(web_command, cwd=ROOT, env=environment))
            while all(process.poll() is None for process in processes):
                time.sleep(0.25)
            return next((process.returncode for process in processes if process.returncode), 0) or 0
        except KeyboardInterrupt:
            return 0
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
