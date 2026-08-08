from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

from packages.upstream import load_inventory, validate_inventory

ROOT = Path(__file__).resolve().parents[1]


def _python_dependencies() -> set[str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    requirements = list(project["dependencies"])
    for values in project.get("optional-dependencies", {}).values():
        requirements.extend(values)
    return {
        re.split(r"[<>=!~;\[]", requirement, maxsplit=1)[0].strip().lower()
        for requirement in requirements
    }


def _npm_dependencies() -> set[str]:
    package = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))
    return {
        name.lower()
        for group in ("dependencies", "devDependencies")
        for name in package.get(group, {})
    }


def main() -> int:
    inventory = load_inventory(ROOT / "config/upstream-projects.yaml")
    errors = validate_inventory(
        inventory,
        repository_root=ROOT,
        required_dependencies=_python_dependencies() | _npm_dependencies(),
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        f"Upstream policy valid: {len(inventory['projects'])} projects; "
        f"{len(inventory['direct_dependencies'])} direct dependencies"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
