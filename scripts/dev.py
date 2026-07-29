from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

from packages.core.config import get_settings

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web"


def run_checked(command: list[str]) -> None:
    print(f"[dev] {' '.join(command)}")
    subprocess.run(command, cwd=ROOT, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local Market Intelligence Lab stack")
    parser.add_argument(
        "--seed",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="seed deterministic demonstration data after migrations",
    )
    parser.add_argument(
        "--worker",
        action="store_true",
        help="start the explicit durable import worker alongside API and frontend",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    settings.ensure_runtime_directories(ROOT)
    npm = shutil.which("npm.cmd" if sys.platform == "win32" else "npm")
    pnpm = shutil.which("pnpm.cmd" if sys.platform == "win32" else "pnpm")
    package_manager = npm or pnpm
    if package_manager is None:
        print(
            "[dev] Node.js with npm or pnpm is required to start the React frontend.",
            file=sys.stderr,
        )
        return 2
    if not (WEB / "node_modules").exists():
        print("[dev] Frontend dependencies are missing; install them in apps/web.", file=sys.stderr)
        return 2

    run_checked([sys.executable, "-m", "alembic", "upgrade", "head"])
    should_seed = settings.seed_demo_data if args.seed is None else args.seed
    if should_seed:
        run_checked([sys.executable, "scripts/seed.py"])

    api_command = [
        sys.executable,
        "-m",
        "uvicorn",
        "apps.api.main:app",
        "--host",
        settings.api_host,
        "--port",
        str(settings.api_port),
        "--reload",
    ]
    web_command = [
        package_manager,
        "run",
        "dev",
        "--",
        "--host",
        settings.web_host,
        "--port",
        str(settings.web_port),
    ]
    processes: list[subprocess.Popen[bytes]] = []
    try:
        print(f"[dev] API: http://{settings.api_host}:{settings.api_port}")
        print(f"[dev] Web: http://{settings.web_host}:{settings.web_port}")
        processes.append(subprocess.Popen(api_command, cwd=ROOT))
        processes.append(subprocess.Popen(web_command, cwd=WEB))
        if args.worker:
            processes.append(
                subprocess.Popen([sys.executable, "-m", "packages.market_data.worker"], cwd=ROOT)
            )
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
        return next((process.returncode for process in processes if process.returncode), 0) or 0
    except KeyboardInterrupt:
        return 0
    finally:
        print("\n[dev] Shutting down local services…")
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
