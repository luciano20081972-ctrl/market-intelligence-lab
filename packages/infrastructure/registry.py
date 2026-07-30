from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

ALLOWED_STATUSES = {"proposed", "evaluating", "active", "deferred", "rejected"}
REQUIRED_FIELDS = {
    "service_name",
    "purpose",
    "status",
    "official_documentation_url",
    "official_pricing_url",
    "verification_date",
    "free_tier_summary",
    "free_tier_limits",
    "expected_monthly_usage",
    "data_classification",
    "credentials_required",
    "production_criticality",
    "export_capability",
    "replacement_options",
    "failure_effect",
    "vendor_lock_in_risk",
    "commercial_use_notes",
    "retention_behavior",
    "budget_alert_threshold",
    "owner",
}
FORBIDDEN_FIELD_PARTS = {"secret", "password", "token", "api_key", "credential_value"}


def load_service_registry(path: Path | None = None) -> list[dict[str, Any]]:
    registry_path = path or Path(__file__).parents[2] / "config" / "infrastructure-services.yaml"
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Infrastructure registry schema_version must be 1")
    services = payload.get("services")
    if not isinstance(services, list):
        raise ValueError("Infrastructure registry services must be a list")
    validated: list[dict[str, Any]] = []
    for service in services:
        if not isinstance(service, dict) or set(service) != REQUIRED_FIELDS:
            raise ValueError("Infrastructure registry entry has missing or unsupported fields")
        if any(part in key.lower() for key in service for part in FORBIDDEN_FIELD_PARTS):
            raise ValueError("Infrastructure registry must not contain secret fields")
        if service["status"] not in ALLOWED_STATUSES:
            raise ValueError("Infrastructure service status is unsupported")
        verified = service["verification_date"]
        if not isinstance(verified, date):
            raise ValueError("Infrastructure verification_date must be an ISO date")
        if not str(service["official_documentation_url"]).startswith("https://") or not str(
            service["official_pricing_url"]
        ).startswith("https://"):
            raise ValueError("Infrastructure vendor URLs must use HTTPS")
        validated.append({**service, "verification_date": verified.isoformat()})
    return validated
