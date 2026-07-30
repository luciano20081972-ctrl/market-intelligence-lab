from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from typing import Any

import jwt
from jwt import InvalidTokenError, PyJWKClient

from packages.core.config import Settings
from packages.database.models import LEGACY_USER_ID

logger = logging.getLogger(__name__)
_VERIFIERS: dict[tuple[str, str], SupabaseJwtVerifier] = {}


class AuthError(ValueError):
    """A deliberately non-sensitive authentication failure."""


@dataclass(frozen=True)
class AuthPrincipal:
    user_id: uuid.UUID
    subject: str
    email: str
    email_verified: bool
    session_id: str | None
    provider: str


def _subject_uuid(subject: str) -> uuid.UUID:
    try:
        return uuid.UUID(subject)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_URL, f"market-intelligence-lab:{subject}")


class SupabaseJwtVerifier:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_url:
            raise AuthError("Authentication service is not configured")
        base_url = settings.supabase_url.rstrip("/")
        if not base_url.startswith("https://"):
            raise AuthError("Supabase URL must use HTTPS")
        self.issuer = f"{base_url}/auth/v1"
        self.audience = settings.supabase_jwt_audience
        self._jwks = PyJWKClient(
            f"{self.issuer}/.well-known/jwks.json",
            cache_keys=True,
            lifespan=300,
            timeout=5,
        )

    def verify(self, token: str) -> AuthPrincipal:
        if len(token) > 16_384:
            raise AuthError("Invalid access token")
        try:
            signing_key = self._jwks.get_signing_key_from_jwt(token)
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except InvalidTokenError as exc:
            logger.info("Access token rejected", extra={"reason": type(exc).__name__})
            raise AuthError("Access token is invalid or expired") from exc
        subject = str(claims.get("sub", "")).strip()
        if not subject:
            raise AuthError("Access token subject is missing")
        email = str(claims.get("email", ""))
        session_id = claims.get("session_id")
        return AuthPrincipal(
            user_id=_subject_uuid(subject),
            subject=subject,
            email=email,
            email_verified=bool(claims.get("email_confirmed_at") or claims.get("email_verified")),
            session_id=str(session_id) if session_id else None,
            provider="supabase",
        )


def authenticate_request(settings: Settings, authorization: str | None) -> AuthPrincipal:
    if settings.auth_mode == "disabled":
        return AuthPrincipal(
            user_id=LEGACY_USER_ID,
            subject="development-user",
            email="developer@localhost.invalid",
            email_verified=True,
            session_id=None,
            provider="development",
        )
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthError("Bearer authentication is required")
    assert settings.supabase_url is not None
    key = (settings.supabase_url, settings.supabase_jwt_audience)
    verifier = _VERIFIERS.get(key)
    if verifier is None:
        verifier = SupabaseJwtVerifier(settings)
        _VERIFIERS[key] = verifier
    return verifier.verify(token)


def token_fingerprint(token: str) -> str:
    """Return a non-reversible short fingerprint suitable for diagnostics."""

    return hashlib.sha256(token.encode()).hexdigest()[:12]
