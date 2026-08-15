"""Run the bounded, opt-in Supabase Auth and application authorization rehearsal."""

from __future__ import annotations

import json
import secrets
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import jwt
from fastapi.testclient import TestClient

from apps.api.main import create_app
from packages.auth.service import SupabaseJwtVerifier
from packages.core.config import Settings
from packages.database.base import Base
from packages.database.models import WorkspaceMembership
from packages.database.session import create_database_engine

PROJECT_REF = "iwfpnrukblptjgvyijdi"
STAGING_ENV = Path(".env.staging.local")


def _require_status(response: httpx.Response, expected: set[int], operation: str) -> None:
    if response.status_code not in expected:
        raise RuntimeError(f"{operation} failed with HTTP {response.status_code}")


def _require_api_status(response: Any, expected: set[int], operation: str) -> None:
    if response.status_code not in expected:
        raise RuntimeError(f"{operation} failed with HTTP {response.status_code}")


def _load_settings() -> Settings:
    if not STAGING_ENV.is_file():
        raise RuntimeError("The ignored staging environment file is unavailable")
    settings = Settings(_env_file=STAGING_ENV)
    if not settings.run_live_supabase_tests:
        raise RuntimeError("MIL_RUN_LIVE_SUPABASE_TESTS is not enabled")
    if settings.supabase_project_ref != PROJECT_REF:
        raise RuntimeError("The configured Supabase project reference does not match staging")
    if not settings.supabase_url or not settings.supabase_url.startswith("https://"):
        raise RuntimeError("The configured Supabase URL is missing or not HTTPS")
    if not settings.supabase_publishable_key or not settings.supabase_secret_key:
        raise RuntimeError("The required Supabase API keys are unavailable")
    return settings


def _create_user(client: httpx.Client, email: str, password: str) -> tuple[str, dict[str, Any]]:
    response = client.post(
        "/auth/v1/admin/users",
        json={
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"validation": "v0.5.1"},
        },
    )
    _require_status(response, {200, 201}, "temporary Auth user creation")
    payload = response.json()
    user_id = str(payload.get("id", ""))
    if not user_id:
        raise RuntimeError("Temporary Auth user creation returned no identifier")
    return user_id, payload


def _sign_in(client: httpx.Client, email: str, password: str) -> tuple[str, str, dict[str, Any]]:
    response = client.post(
        "/auth/v1/token",
        params={"grant_type": "password"},
        json={"email": email, "password": password},
    )
    _require_status(response, {200}, "password sign-in")
    payload = response.json()
    access_token = str(payload.get("access_token", ""))
    refresh_token = str(payload.get("refresh_token", ""))
    if not access_token or not refresh_token:
        raise RuntimeError("Password sign-in returned an incomplete session")
    return access_token, refresh_token, payload


def _refresh(client: httpx.Client, refresh_token: str) -> tuple[str, str]:
    response = client.post(
        "/auth/v1/token",
        params={"grant_type": "refresh_token"},
        json={"refresh_token": refresh_token},
    )
    _require_status(response, {200}, "session refresh")
    payload = response.json()
    access_token = str(payload.get("access_token", ""))
    rotated_refresh_token = str(payload.get("refresh_token", ""))
    if not access_token or not rotated_refresh_token:
        raise RuntimeError("Session refresh returned an incomplete session")
    return access_token, rotated_refresh_token


def _sign_out(client: httpx.Client, access_token: str) -> None:
    response = client.post(
        "/auth/v1/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    _require_status(response, {200, 204}, "sign-out")


def _delete_user(client: httpx.Client, user_id: str) -> None:
    response = client.delete(f"/auth/v1/admin/users/{user_id}")
    _require_status(response, {200, 204}, "temporary Auth user deletion")


def _verify_token(verifier: SupabaseJwtVerifier, token: str, expected_user_id: str) -> None:
    principal = verifier.verify(token)
    if principal.subject != expected_user_id:
        raise RuntimeError("JWT subject does not match the temporary Auth user")
    claims = jwt.decode(token, options={"verify_signature": False})
    if claims.get("iss") != verifier.issuer:
        raise RuntimeError("JWT issuer does not match staging")
    audience = claims.get("aud")
    valid_audience = (
        verifier.audience in audience
        if isinstance(audience, list)
        else (audience == verifier.audience)
    )
    if not valid_audience:
        raise RuntimeError("JWT audience does not match the application")
    if int(claims.get("exp", 0)) <= int(time.time()):
        raise RuntimeError("JWT is already expired")
    if claims.get("sub") != expected_user_id:
        raise RuntimeError("JWT subject claim does not match staging")


def _validate_data_api_denial(public_client: httpx.Client, access_token: str | None = None) -> None:
    headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
    response = public_client.get(
        "/rest/v1/assets",
        params={"select": "id", "limit": "1"},
        headers=headers,
    )
    _require_status(response, {401, 403}, "deny-by-default Data API request")


def _validate_application_authorization(
    settings: Settings, token_a: str, token_b: str
) -> dict[str, bool]:
    with tempfile.TemporaryDirectory(prefix="mil-v051-auth-") as temp_dir:
        database_path = Path(temp_dir) / "authorization.sqlite"
        database_url = f"sqlite:///{database_path.as_posix()}"
        engine = create_database_engine(database_url)
        Base.metadata.create_all(engine)
        app_settings = Settings(
            environment="test",
            database_url=database_url,
            seed_demo_data=False,
            auth_mode="supabase",
            supabase_project_ref=PROJECT_REF,
            supabase_url=settings.supabase_url,
            supabase_jwt_audience=settings.supabase_jwt_audience,
        )
        app = create_app(app_settings, engine)
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}
        with TestClient(app) as client:
            _require_api_status(client.get("/api/v1/auth/me"), {401}, "missing-token rejection")
            _require_api_status(
                client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": "Bearer not-a-valid-token"},
                ),
                {401},
                "invalid-token rejection",
            )

            workspace_a_response = client.post(
                "/api/v1/workspaces",
                headers=headers_a,
                json={"name": "Temporary Workspace A", "slug": f"temp-a-{uuid.uuid4().hex}"},
            )
            workspace_b_response = client.post(
                "/api/v1/workspaces",
                headers=headers_b,
                json={"name": "Temporary Workspace B", "slug": f"temp-b-{uuid.uuid4().hex}"},
            )
            _require_api_status(workspace_a_response, {201}, "Workspace A creation")
            _require_api_status(workspace_b_response, {201}, "Workspace B creation")
            workspace_a = str(workspace_a_response.json()["id"])
            workspace_b = str(workspace_b_response.json()["id"])

            _require_api_status(
                client.get("/api/v1/auth/me", headers=headers_a),
                {200},
                "authenticated /auth/me",
            )
            _require_api_status(
                client.get("/api/v1/users/me", headers=headers_a),
                {200},
                "authenticated /users/me",
            )
            _require_api_status(
                client.get(f"/api/v1/workspaces/{workspace_b}", headers=headers_a),
                {404},
                "cross-workspace read denial",
            )
            _require_api_status(
                client.patch(
                    f"/api/v1/workspaces/{workspace_b}",
                    headers=headers_a,
                    json={"name": "Denied"},
                ),
                {404},
                "cross-workspace write denial",
            )
            _require_api_status(
                client.get(f"/api/v1/workspaces/{uuid.uuid4()}", headers=headers_a),
                {404},
                "guessed-ID denial",
            )

            with app.state.session_factory() as session:
                token_b_claims = jwt.decode(token_b, options={"verify_signature": False})
                user_b_id = uuid.UUID(token_b_claims["sub"])
                viewer = WorkspaceMembership(
                    workspace_id=uuid.UUID(workspace_a),
                    user_id=user_b_id,
                    role="viewer",
                )
                session.add(viewer)
                session.commit()
                viewer_membership_id = str(viewer.id)

            _require_api_status(
                client.patch(
                    f"/api/v1/workspaces/{workspace_a}",
                    headers=headers_b,
                    json={"name": "Viewer denied"},
                ),
                {403},
                "viewer mutation denial",
            )
            _require_api_status(
                client.patch(
                    f"/api/v1/workspaces/{workspace_a}/members/{viewer_membership_id}",
                    headers=headers_a,
                    json={"role": "member"},
                ),
                {200},
                "owner membership control",
            )
            _require_api_status(
                client.patch(
                    f"/api/v1/workspaces/{workspace_a}",
                    headers=headers_a,
                    json={"name": "Temporary Workspace A validated"},
                ),
                {200},
                "owner workspace update",
            )
            audit_response = client.get(
                f"/api/v1/workspaces/{workspace_a}/audit-events", headers=headers_a
            )
            _require_api_status(audit_response, {200}, "audit-event read")
            audit_payload = audit_response.json()
            if audit_payload["total"] < 3:
                raise RuntimeError("Expected workspace audit events were not created")
            serialized_audit = json.dumps(audit_payload).lower()
            sensitive_terms = ("authorization", "password", "refresh_token")
            if any(term in serialized_audit for term in sensitive_terms):
                raise RuntimeError("Sensitive Auth material appeared in audit output")

        engine.dispose()
    return {
        "auth_me": True,
        "users_me": True,
        "cross_workspace_read_denied": True,
        "cross_workspace_write_denied": True,
        "viewer_mutation_denied": True,
        "owner_membership_control": True,
        "guessed_id_denied": True,
        "audit_created_and_redacted": True,
    }


def main() -> None:
    settings = _load_settings()
    assert settings.supabase_url is not None
    assert settings.supabase_publishable_key is not None
    assert settings.supabase_secret_key is not None
    base_url = settings.supabase_url.rstrip("/")
    public_client = httpx.Client(
        base_url=base_url,
        headers={"apikey": settings.supabase_publishable_key},
        timeout=15,
    )
    admin_client = httpx.Client(
        base_url=base_url,
        headers={
            "apikey": settings.supabase_secret_key,
            "Authorization": f"Bearer {settings.supabase_secret_key}",
        },
        timeout=15,
    )
    created_users: list[str] = []
    active_tokens: list[str] = []
    results: dict[str, Any] = {}
    try:
        auth_settings_response = public_client.get("/auth/v1/settings")
        _require_status(auth_settings_response, {200}, "Auth settings discovery")
        auth_settings = auth_settings_response.json()
        results["email_confirmation_setting_read"] = isinstance(
            auth_settings.get("mailer_autoconfirm"), bool
        )

        _validate_data_api_denial(public_client)
        results["publishable_data_api_denied"] = True

        unique = uuid.uuid4().hex
        email_a = f"mil-v051-a-{unique}@example.invalid"
        email_b = f"mil-v051-b-{unique}@example.invalid"
        password_a = secrets.token_urlsafe(32)
        password_b = secrets.token_urlsafe(32)
        user_a, _ = _create_user(admin_client, email_a, password_a)
        created_users.append(user_a)
        user_b, _ = _create_user(admin_client, email_b, password_b)
        created_users.append(user_b)

        token_a, refresh_a, _ = _sign_in(public_client, email_a, password_a)
        token_b, _, _ = _sign_in(public_client, email_b, password_b)
        active_tokens.extend((token_a, token_b))
        verifier = SupabaseJwtVerifier(settings)
        _verify_token(verifier, token_a, user_a)
        _verify_token(verifier, token_b, user_b)
        results["password_sign_in"] = True
        results["jwt_signature_and_claims"] = True

        _validate_data_api_denial(public_client, token_a)
        results["authenticated_data_api_denied"] = True

        refreshed_access, refreshed_refresh = _refresh(public_client, refresh_a)
        active_tokens[0] = refreshed_access
        _verify_token(verifier, refreshed_access, user_a)
        results["session_refresh"] = True

        results["application_authorization"] = _validate_application_authorization(
            settings, refreshed_access, token_b
        )

        _sign_out(public_client, refreshed_access)
        active_tokens.remove(refreshed_access)
        refresh_after_logout = public_client.post(
            "/auth/v1/token",
            params={"grant_type": "refresh_token"},
            json={"refresh_token": refreshed_refresh},
        )
        _require_status(refresh_after_logout, {400, 401}, "post-logout refresh rejection")
        results["sign_out_and_refresh_revocation"] = True
    finally:
        for access_token in active_tokens:
            try:
                _sign_out(public_client, access_token)
            except RuntimeError:
                pass
        cleanup_failures = 0
        for user_id in reversed(created_users):
            try:
                _delete_user(admin_client, user_id)
            except RuntimeError:
                cleanup_failures += 1
        public_client.close()
        admin_client.close()
        if cleanup_failures:
            raise RuntimeError(
                f"Temporary Auth user cleanup had {cleanup_failures} safe failure(s)"
            )
    results["temporary_users_deleted"] = True
    print(json.dumps(results, sort_keys=True))


if __name__ == "__main__":
    main()
