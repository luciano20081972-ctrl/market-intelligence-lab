from __future__ import annotations

import copy
from pathlib import Path
from typing import cast

from packages.upstream import load_inventory, validate_inventory

ROOT = Path(__file__).resolve().parents[1]


def _inventory() -> dict[str, object]:
    return load_inventory(ROOT / "config/upstream-projects.yaml")


def test_repository_upstream_inventory_is_valid() -> None:
    inventory = _inventory()
    assert validate_inventory(inventory, repository_root=ROOT) == []
    assert len(inventory["projects"]) == 9  # type: ignore[arg-type]


def test_unknown_license_is_rejected() -> None:
    inventory = copy.deepcopy(_inventory())
    inventory["projects"][0]["license"] = "UNKNOWN"  # type: ignore[index]
    assert any(
        "unknown license" in error for error in validate_inventory(inventory, repository_root=ROOT)
    )


def test_missing_third_party_notice_is_rejected(tmp_path: Path) -> None:
    inventory = copy.deepcopy(_inventory())
    errors = validate_inventory(inventory, repository_root=tmp_path)
    assert any("third-party notice is missing" in error for error in errors)


def test_agpl_and_gpl_vendoring_are_rejected(tmp_path: Path) -> None:
    source = tmp_path / "restricted.py"
    source.write_text("print('restricted')\n", encoding="utf-8")
    inventory = copy.deepcopy(_inventory())
    for license_id in ("AGPL-3.0-only", "GPL-3.0"):
        project = inventory["projects"][0]  # type: ignore[index]
        project["license"] = license_id
        project["integration_category"] = "reference_only"
        project["source_files_used"] = ["restricted.py"]
        project["source_file_hashes"] = {
            "restricted.py": "de9a79d8dbf7fdedb1159f4f2ed8c9a759a268396a3c64f472008f74cce49f84"
        }
        errors = validate_inventory(inventory, repository_root=tmp_path)
        assert any("restricted-license source" in error for error in errors)


def test_copied_file_requires_valid_provenance_hash(tmp_path: Path) -> None:
    source = tmp_path / "adapted.py"
    source.write_text("value = 1\n", encoding="utf-8")
    inventory = copy.deepcopy(_inventory())
    project = inventory["projects"][0]  # type: ignore[index]
    project["source_files_used"] = ["adapted.py"]
    project["source_file_hashes"] = {"adapted.py": "0" * 64}
    errors = validate_inventory(inventory, repository_root=tmp_path)
    assert any("hash mismatch" in error for error in errors)


def test_dependency_versions_are_exactly_pinned() -> None:
    inventory = copy.deepcopy(_inventory())
    projects = cast(list[dict[str, object]], inventory["projects"])
    project = next(item for item in projects if item["integration_category"] == "dependency")
    project["dependency_version"] = ">=5"
    errors = validate_inventory(inventory, repository_root=ROOT)
    assert any("exactly pinned" in error for error in errors)


def test_required_dependency_consistency() -> None:
    inventory = _inventory()
    errors = validate_inventory(
        inventory,
        repository_root=ROOT,
        required_dependencies={
            "edgartools",
            "numpy",
            "quantstats",
            "scikit-learn",
            "scipy",
            "skfolio",
            "statsmodels",
            "react",
        },
    )
    assert errors == []
    errors = validate_inventory(
        inventory, repository_root=ROOT, required_dependencies={"missing-package"}
    )
    assert any("missing direct dependencies" in error for error in errors)
