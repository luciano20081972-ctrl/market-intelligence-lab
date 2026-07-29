from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web"


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    print(f"[verify] {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    package_manager = shutil.which("pnpm.cmd" if sys.platform == "win32" else "pnpm")
    if package_manager is None:
        raise RuntimeError("pnpm is required for frontend verification")
    run([sys.executable, "-m", "pytest"])
    run([sys.executable, "-m", "ruff", "check", "."])
    run([sys.executable, "-m", "mypy", "apps", "packages", "scripts"])
    run([package_manager, "run", "typecheck"], cwd=WEB)
    run([package_manager, "test"], cwd=WEB)
    run([package_manager, "run", "build"], cwd=WEB)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
