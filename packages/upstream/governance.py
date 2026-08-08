from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

ALLOWED_CATEGORIES = {
    "dependency",
    "adapted_permissive_code",
    "external_service",
    "optional_engine",
    "reference_only",
    "rejected",
}
ALLOWED_LICENSES = {
    "MIT",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "Apache-2.0",
    "LGPL-3.0",
    "LGPL-3.0-only",
    "LGPL-3.0-or-later",
    "GPL-2.0",
    "GPL-3.0",
    "AGPL-3.0",
    "AGPL-3.0-only",
    "Proprietary",
}
RESTRICTED_LICENSE_PREFIXES = ("GPL-", "AGPL-", "Proprietary")
REQUIRED_PROJECT_FIELDS = {
    "name",
    "repository_url",
    "reviewed_revision",
    "license",
    "license_file_url",
    "copyright_holder",
    "integration_category",
    "approved_use",
    "prohibited_use",
    "attribution_requirements",
    "source_files_used",
    "source_file_hashes",
    "modifications_made",
    "dependency_version",
    "replacement_strategy",
    "maintenance_status",
    "last_review_date",
    "security_status",
    "commercial_use_status",
    "network_service_obligations",
    "patent_provisions",
    "trademark_restrictions",
}


class GovernanceError(ValueError):
    pass


def load_inventory(path: Path | str = Path("config/upstream-projects.yaml")) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GovernanceError("Upstream inventory must be a mapping")
    return value


def validate_inventory(
    inventory: dict[str, Any],
    *,
    repository_root: Path = Path("."),
    required_dependencies: set[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    projects = inventory.get("projects")
    dependencies = inventory.get("direct_dependencies")
    notices_path = repository_root / "THIRD_PARTY_NOTICES.md"
    notices = notices_path.read_text(encoding="utf-8").lower() if notices_path.is_file() else ""
    if not isinstance(projects, list) or not projects:
        return ["projects must be a non-empty list"]
    if not isinstance(dependencies, list):
        errors.append("direct_dependencies must be a list")
        dependencies = []
    dependency_names = {
        str(item.get("name", "")).lower()
        for item in dependencies
        if isinstance(item, dict)
    }
    if required_dependencies:
        missing = sorted(
            name.lower()
            for name in required_dependencies
            if name.lower() not in dependency_names
        )
        if missing:
            errors.append(f"missing direct dependencies: {', '.join(missing)}")
    for project in projects:
        if not isinstance(project, dict):
            errors.append("project record must be a mapping")
            continue
        name = str(project.get("name", "<unnamed>"))
        missing_fields = sorted(REQUIRED_PROJECT_FIELDS - project.keys())
        if missing_fields:
            errors.append(f"{name}: missing fields {', '.join(missing_fields)}")
        license_id = str(project.get("license", ""))
        category = str(project.get("integration_category", ""))
        if license_id not in ALLOWED_LICENSES:
            errors.append(f"{name}: unknown license {license_id!r}")
        if category not in ALLOWED_CATEGORIES:
            errors.append(f"{name}: invalid integration category {category!r}")
        if license_id.startswith(("GPL-", "AGPL-")) and category not in {
            "reference_only",
            "rejected",
        }:
            errors.append(f"{name}: copyleft project must be reference_only or rejected")
        if license_id == "Proprietary" and category not in {"reference_only", "rejected"}:
            errors.append(f"{name}: restricted project must be reference_only or rejected")
        files = project.get("source_files_used", [])
        hashes = project.get("source_file_hashes", {})
        if files and not project.get("attribution_requirements"):
            errors.append(f"{name}: copied/adapted files require attribution")
        for relative in files if isinstance(files, list) else []:
            path = (repository_root / str(relative)).resolve()
            try:
                path.relative_to(repository_root.resolve())
            except ValueError:
                errors.append(f"{name}: source file escapes repository: {relative}")
                continue
            if not path.is_file():
                errors.append(f"{name}: source file is missing: {relative}")
                continue
            expected = hashes.get(relative) if isinstance(hashes, dict) else None
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if not expected or not re.fullmatch(r"[0-9a-f]{64}", str(expected)):
                errors.append(f"{name}: source file hash missing or invalid: {relative}")
            elif expected != actual:
                errors.append(f"{name}: source file hash mismatch: {relative}")
        if license_id.startswith(RESTRICTED_LICENSE_PREFIXES) and files:
            errors.append(f"{name}: restricted-license source must not be vendored")
        dependency_version = project.get("dependency_version")
        if category == "dependency":
            if not dependency_version or re.search(r"[<>=~^]", str(dependency_version)):
                errors.append(f"{name}: dependency version must be exactly pinned")
            notice_name = name.rsplit("/", maxsplit=1)[-1].lower()
            if notice_name not in notices:
                errors.append(f"{name}: third-party notice is missing")
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            errors.append("direct dependency record must be a mapping")
            continue
        license_id = str(dependency.get("license", ""))
        if not dependency.get("name") or not dependency.get("version"):
            errors.append("direct dependency requires name and version")
        if license_id not in ALLOWED_LICENSES:
            errors.append(f"{dependency.get('name', '<unnamed>')}: unknown license {license_id!r}")
    return errors
