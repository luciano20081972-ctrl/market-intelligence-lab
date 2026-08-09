from __future__ import annotations

from typing import Any


class GoogleAuthorizedHttpTransport:
    """Cloud Run v2 transport using Application Default Credentials or WIF."""

    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        try:
            import google.auth  # type: ignore[import-untyped]
            from google.auth.transport.requests import (  # type: ignore[import-untyped]
                AuthorizedSession,
            )
        except ImportError as exc:
            raise RuntimeError("google-auth is required by the Dell cloud orchestrator") from exc
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self._session = AuthorizedSession(credentials)
        self._timeout_seconds = timeout_seconds
        self._base_url = "https://run.googleapis.com"

    def _json(self, response: Any) -> dict[str, Any]:
        response.raise_for_status()
        value = response.json()
        if not isinstance(value, dict):
            raise RuntimeError("Google Cloud response was not a JSON object")
        return value

    def post(self, path: str, payload: dict[str, Any], *, request_id: str) -> dict[str, Any]:
        response = self._session.post(
            f"{self._base_url}{path}",
            json=payload,
            headers={"X-MIL-Submission-Key": request_id[:160]},
            timeout=self._timeout_seconds,
        )
        return self._json(response)

    def get(self, path: str) -> dict[str, Any]:
        response = self._session.get(f"{self._base_url}{path}", timeout=self._timeout_seconds)
        return self._json(response)
