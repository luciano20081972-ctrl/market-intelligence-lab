from __future__ import annotations

import os
import subprocess
import sys

from packages.core.config import get_settings


def main() -> None:
    settings = get_settings()
    settings.ensure_runtime_directories()
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    if settings.seed_demo_data:
        subprocess.run([sys.executable, "scripts/seed.py"], check=True)
    os.execvp(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "apps.api.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ],
    )


if __name__ == "__main__":
    main()
