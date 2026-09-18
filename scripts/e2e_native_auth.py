"""Run real-browser native auth acceptance against disposable local data only."""

from __future__ import annotations

import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

from packages.auth.bootstrap import ensure_legacy_workspace
from packages.auth.native import enroll
from packages.database.base import Base
from packages.database.models import LEGACY_USER_ID, Workspace, WorkspaceMembership
from packages.database.session import create_database_engine, make_session_factory

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> int:
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node.js required")
    with tempfile.TemporaryDirectory(prefix="mil-native-e2e-") as temporary:
        api_port, web_port = free_port(), free_port()
        database_url = f"sqlite:///{Path(temporary).as_posix()}/acceptance.db"
        engine = create_database_engine(database_url)
        Base.metadata.create_all(engine)
        factory = make_session_factory(engine)
        with factory.begin() as session:
            ensure_legacy_workspace(session)
            second = Workspace(
                name="Second acceptance workspace",
                slug="acceptance-second",
                created_by_user_id=LEGACY_USER_ID,
            )
            session.add(second)
            session.flush()
            session.add(
                WorkspaceMembership(workspace_id=second.id, user_id=LEGACY_USER_ID, role="owner")
            )
        password = secrets.token_urlsafe(24)
        enroll(factory, engine, LEGACY_USER_ID, "acceptance-owner", password)
        engine.dispose()
        api_url, web_url = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{web_port}"
        environment = {
            key: value for key, value in os.environ.items() if not key.startswith(("MIL_", "VITE_"))
        }
        environment.update(
            {
                "MIL_ENVIRONMENT": "test",
                "MIL_AUTH_MODE": "native",
                "MIL_DATABASE_URL": database_url,
                "MIL_MIGRATION_DATABASE_URL": "",
                "MIL_AUTH_ALLOWED_ORIGINS": f'["{web_url}"]',
                "MIL_CORS_ORIGINS": f'["{web_url}"]',
                "MIL_SENTRY_DSN": "",
                "MIL_SEED_DEMO_DATA": "false",
                "VITE_API_BASE_URL": api_url,
                "VITE_AUTH_MODE": "native",
                "VITE_SENTRY_DSN": "",
                "MIL_E2E_URL": web_url,
                "MIL_E2E_API_URL": api_url,
                "MIL_E2E_PASSWORD": password,
            }
        )
        # The database URL is not needed by migration tooling in this metadata fixture.
        environment.pop("MIL_MIGRATION_DATABASE_URL")
        commands = [
            (
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "apps.api.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(api_port),
                    "--no-access-log",
                    "--no-proxy-headers",
                ],
                ROOT,
            ),
            (
                [
                    node,
                    str(WEB / "node_modules/vite/bin/vite.js"),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(web_port),
                    "--strictPort",
                ],
                WEB,
            ),
        ]
        processes = []
        try:
            for command, cwd in commands:
                processes.append(
                    subprocess.Popen(
                        command,
                        cwd=cwd,
                        env=environment,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                )
            deadline = time.monotonic() + 60
            while True:
                if any(process.poll() is not None for process in processes):
                    raise RuntimeError("Disposable test server failed to start")
                try:
                    if httpx.get(api_url + "/health/live", timeout=1).status_code == 200 and (
                        httpx.get(web_url, timeout=1).status_code == 200
                    ):
                        break
                except httpx.HTTPError:
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError("Disposable test servers did not become ready")
                time.sleep(0.25)
            return subprocess.run(
                [
                    node,
                    str(WEB / "node_modules/@playwright/test/cli.js"),
                    "test",
                    "--config",
                    "playwright.native.config.ts",
                ],
                cwd=WEB,
                env=environment,
                check=False,
            ).returncode
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
