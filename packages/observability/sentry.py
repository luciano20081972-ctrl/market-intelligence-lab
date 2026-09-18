from __future__ import annotations

import importlib
from typing import Any

from packages.core.config import Settings

SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "password",
    "current_password",
    "new_password",
    "password_hash",
    "access_token",
    "session_token",
    "token",
    "api_key",
    "apikey",
    "supabase_service_role_key",
    "provider_key",
}


def _scrub(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any] | None:
    request = event.get("request")
    if isinstance(request, dict):
        if "/api/v1/auth/" in str(request.get("url", "")):
            return None  # Authentication has local, server-authored audit events.
        request.pop("data", None)
        request.pop("cookies", None)
        request.pop("query_string", None)
        if isinstance(request.get("url"), str):
            request["url"] = request["url"].split("?", 1)[0]
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {
                key: "[Filtered]" if key.lower() in SENSITIVE_KEYS else value
                for key, value in headers.items()
            }
    return event


def configure_sentry(settings: Settings) -> bool:
    if not settings.sentry_dsn:
        return False
    try:
        sentry_sdk = importlib.import_module("sentry_sdk")
    except ImportError:
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=f"market-intelligence-lab@{settings.version}",
        send_default_pii=False,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        before_send=_scrub,
        max_request_body_size="never",
        include_local_variables=False,
    )
    return True
