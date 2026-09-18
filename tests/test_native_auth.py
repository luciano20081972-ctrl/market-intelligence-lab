from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select

from apps.api.main import create_app
from packages.auth import AuthError, native
from packages.core.config import Settings
from packages.core.time import utc_now
from packages.database.models import (
    LEGACY_USER_ID,
    AuditEvent,
    AuthRateBucket,
    NativeCredential,
    NativeSession,
    UserProfile,
    Workspace,
    WorkspaceMembership,
)
from packages.database.session import make_session_factory

PASSWORD = "disposable-test-password-7!"  # noqa: S105
ORIGIN = "https://mil.example.test:8443"


@pytest.fixture
def auth(engine: Engine):  # type: ignore[no-untyped-def]
    factory = make_session_factory(engine)
    native.enroll(factory, engine, LEGACY_USER_ID, "owner", PASSWORD)
    settings = Settings(environment="test", auth_mode="native", auth_allowed_origins=[ORIGIN])
    with TestClient(create_app(settings, engine), headers={"Origin": ORIGIN}) as client:
        yield client, factory, settings


def sign_in(client: TestClient) -> str:
    response = client.post("/api/v1/auth/login", json={"login": "OWNER", "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]  # type: ignore[no-any-return]


def test_login_local_identity_and_no_secrets(auth, caplog):  # type: ignore[no-untyped-def]
    client, factory, _ = auth
    token = sign_in(client)
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["id"] == str(LEGACY_USER_ID)
    assert response.json()["provider"] == "native"
    assert "set-cookie" not in response.headers
    assert response.headers["cache-control"] == "no-store"
    with factory() as session:
        active = session.scalar(select(NativeSession))
        assert active.token_digest == hashlib.sha256(token.encode()).hexdigest()
        assert active.token_digest != token
        encoded = session.get(NativeCredential, LEGACY_USER_ID).password_hash
        assert encoded.startswith("$argon2id$v=19$m=65536,t=3,p=1$")
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.action == "auth.sign_in_succeeded")
        ).all()
        assert len(events) == 1
        serialized = str([event.details for event in events])
        assert all(secret not in serialized for secret in (token, PASSWORD, encoded))
    assert token not in caplog.text and PASSWORD not in caplog.text and encoded not in caplog.text


@pytest.mark.parametrize("identifier,password", [("owner", "wrong"), ("unknown", PASSWORD)])
def test_generic_failure(auth, identifier: str, password: str):  # type: ignore[no-untyped-def]
    client, _, _ = auth
    response = client.post("/api/v1/auth/login", json={"login": identifier, "password": password})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials or session"}


def test_disabled_login_and_session(auth):  # type: ignore[no-untyped-def]
    client, factory, _ = auth
    token = sign_in(client)
    with factory.begin() as session:
        session.get(UserProfile, LEGACY_USER_ID).is_disabled = True
    assert (
        client.post("/api/v1/auth/login", json={"login": "owner", "password": PASSWORD}).status_code
        == 401
    )
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"login": "owner"},
        {"login": "owner", "password": 123},
        {"login": "owner", "password": "x" * 129},
        {"login": "owner", "password": PASSWORD, "extra": 1},
    ],
)
def test_malformed_credentials_redacted(auth, payload):  # type: ignore[no-untyped-def]
    client, _, _ = auth
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid authentication request"}


@pytest.mark.parametrize("mutation", ["idle", "absolute", "revoked", "version"])
def test_session_invalidation(auth, mutation: str):  # type: ignore[no-untyped-def]
    client, factory, _ = auth
    token = sign_in(client)
    with factory.begin() as session:
        active = session.scalar(select(NativeSession))
        past = utc_now() - timedelta(seconds=1)
        if mutation == "idle":
            active.idle_expires_at = past
        elif mutation == "absolute":
            active.absolute_expires_at = past
        elif mutation == "revoked":
            active.revoked_at = utc_now()
        else:
            session.get(NativeCredential, LEGACY_USER_ID).version += 1
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )


@pytest.mark.parametrize("token", ["", "abc", "x" * 43, "x" * 10000, "bad.token.jwt"])
def test_bad_tokens(auth, token: str):  # type: ignore[no-untyped-def]
    client, _, _ = auth
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )


def test_logout_fresh_verifier_and_password_change(auth, engine: Engine):  # type: ignore[no-untyped-def]
    client, factory, settings = auth
    token = sign_in(client)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    with TestClient(create_app(settings, engine)) as second:
        assert second.get("/api/v1/auth/me", headers=headers).status_code == 401
    first, other = sign_in(client), sign_in(client)
    response = client.post(
        "/api/v1/auth/password",
        headers={"Authorization": f"Bearer {first}"},
        json={"current_password": PASSWORD, "new_password": "changed-test-password-9!"},
    )
    assert response.status_code == 204
    for value in (first, other):
        with pytest.raises(AuthError):
            native.authenticate(factory, settings, f"Bearer {value}")
    assert (
        client.post(
            "/api/v1/auth/login", json={"login": "owner", "password": "changed-test-password-9!"}
        ).status_code
        == 200
    )


def test_reset_identity_and_collision(auth, engine: Engine):  # type: ignore[no-untyped-def]
    client, factory, settings = auth
    token = sign_in(client)
    with factory() as session:
        profile = session.get(UserProfile, LEGACY_USER_ID)
        before = (profile.id, profile.auth_subject, profile.email)
        ownership = [(w.id, w.created_by_user_id) for w in session.scalars(select(Workspace))]
        roles = [(m.id, m.user_id, m.role) for m in session.scalars(select(WorkspaceMembership))]
        history = set(session.scalars(select(AuditEvent.id)))
    native.enroll(factory, engine, LEGACY_USER_ID, "owner", PASSWORD, reset=True)
    with factory() as session:
        profile = session.get(UserProfile, LEGACY_USER_ID)
        assert before == (profile.id, profile.auth_subject, profile.email)
        assert ownership == [
            (w.id, w.created_by_user_id) for w in session.scalars(select(Workspace))
        ]
        assert roles == [
            (m.id, m.user_id, m.role) for m in session.scalars(select(WorkspaceMembership))
        ]
        assert history.issubset(set(session.scalars(select(AuditEvent.id))))
    with pytest.raises(AuthError):
        native.authenticate(factory, settings, f"Bearer {token}")
    with pytest.raises(AuthError):
        native.enroll(factory, engine, uuid.uuid4(), "other", PASSWORD)
    with pytest.raises(AuthError):
        native.enroll(factory, engine, LEGACY_USER_ID, "owner", PASSWORD)


@pytest.mark.parametrize("kind", ["account", "source", "global"])
def test_throttles(auth, kind: str):  # type: ignore[no-untyped-def]
    _, factory, settings = auth
    settings = settings.model_copy(update={f"auth_{kind}_limit": 2})
    for i in range(2):
        native.throttle(
            factory,
            settings,
            "same" if kind == "account" else str(i),
            "same" if kind == "source" else str(i),
        )
    with pytest.raises(native.AuthBusy):
        native.throttle(
            factory,
            settings,
            "same" if kind == "account" else "new",
            "same" if kind == "source" else "new",
        )
    with factory.begin() as session:
        for row in session.scalars(select(AuthRateBucket)):
            row.expires_at = utc_now() - timedelta(seconds=1)
    native.throttle(factory, settings, "new", "new")
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(AuthRateBucket)) <= 3


def test_bounded_hashing(engine: Engine) -> None:
    with native.hash_slot(engine), native.hash_slot(engine), pytest.raises(native.AuthBusy):
        with native.hash_slot(engine):
            pass
    with native.hash_slot(engine):
        pass


def test_forwarded_headers_cannot_bypass_limits(auth):  # type: ignore[no-untyped-def]
    client, _, settings = auth
    settings.auth_source_limit = 2
    for i in range(3):
        response = client.post(
            "/api/v1/auth/login",
            headers={"X-Forwarded-For": f"10.0.0.{i}"},
            json={"login": f"unknown{i}", "password": PASSWORD},
        )
        assert response.status_code == (401 if i < 2 else 429)


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.test"},
        {"Origin": "null"},
        {"Origin": "https://mil.example.test"},
        {"Cookie": "access_token=secret"},
    ],
)
def test_boundary(auth, headers):  # type: ignore[no-untyped-def]
    client, _, _ = auth
    response = client.post(
        "/api/v1/auth/login", headers=headers, json={"login": "owner", "password": PASSWORD}
    )
    assert response.status_code in (400, 403)


def test_query_and_oversize_body_rejection(auth):  # type: ignore[no-untyped-def]
    client, _, _ = auth
    assert client.post("/api/v1/auth/login?password=secret").status_code == 400
    assert client.get("/api/v1/auth/me?access_token=secret").status_code == 400
    assert client.post("/api/v1/auth/login", content="x" * 5000).status_code == 413


def test_no_provider_calls_and_readiness(auth, monkeypatch):  # type: ignore[no-untyped-def]
    client, _, _ = auth

    def unavailable(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("External auth must never be called")

    monkeypatch.setattr("packages.auth.service.SupabaseJwtVerifier", unavailable)
    token = sign_in(client)
    assert client.get("/api/v1/auth/health").status_code == 200
    assert client.get("/health/ready").status_code == 200
    assert (
        client.post(
            "/api/v1/auth/events", json={"action": "auth.sign_in_succeeded", "result": "success"}
        ).status_code
        == 404
    )
    assert (
        client.get("/api/v1/workspaces", headers={"Authorization": f"Bearer {token}"}).status_code
        == 200
    )


def test_rbac_and_workspace_denial(auth):  # type: ignore[no-untyped-def]
    client, factory, _ = auth
    token = sign_in(client)
    headers = {"Authorization": f"Bearer {token}"}
    assert (
        client.get(
            "/api/v1/watchlists", headers={**headers, "X-Workspace-ID": str(uuid.uuid4())}
        ).status_code
        == 404
    )
    with factory.begin() as session:
        session.scalar(
            select(WorkspaceMembership).where(WorkspaceMembership.user_id == LEGACY_USER_ID)
        ).role = "viewer"
    assert (
        client.post("/api/v1/watchlists", headers=headers, json={"name": "forbidden"}).status_code
        == 403
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"auth_mode": "disabled"},
        {"auth_allowed_origins": ["http://mil.example.test"]},
        {"auth_allowed_origins": ["https://mil.example.test/path"]},
        {"auth_allowed_origins": []},
        {"auth_idle_seconds": 3600, "auth_absolute_seconds": 1800},
    ],
)
def test_production_fail_closed(changes):  # type: ignore[no-untyped-def]
    values = dict(
        environment="production",
        auth_mode="native",
        database_url="postgresql://localhost/test",
        auth_allowed_origins=[ORIGIN],
        cors_origins=[ORIGIN],
    )
    values.update(changes)
    with pytest.raises(ValueError):
        Settings(**values)


def test_last_seen_updates_are_bounded(auth):  # type: ignore[no-untyped-def]
    client, factory, settings = auth
    token = sign_in(client)
    with factory() as session:
        issued = session.scalar(select(NativeSession)).last_seen_at
    for _ in range(3):
        native.authenticate(factory, settings, f"Bearer {token}")
    with factory() as session:
        assert session.scalar(select(NativeSession)).last_seen_at == issued
    with factory.begin() as session:
        row = session.scalar(select(NativeSession))
        row.last_seen_at = utc_now() - timedelta(seconds=120)
        row.absolute_expires_at = utc_now() + timedelta(seconds=600)
    native.authenticate(factory, settings, f"Bearer {token}")
    with factory() as session:
        row = session.scalar(select(NativeSession))
        assert row.last_seen_at > issued
        assert row.idle_expires_at <= row.absolute_expires_at


def test_sessions_are_capped_and_expired_rows_cleaned(auth):  # type: ignore[no-untyped-def]
    client, factory, settings = auth
    settings.auth_account_limit = 30
    oldest = sign_in(client)
    for _ in range(10):
        sign_in(client)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(NativeSession)) == 10
    with pytest.raises(AuthError):
        native.authenticate(factory, settings, f"Bearer {oldest}")
    with factory.begin() as session:
        for row in session.scalars(select(NativeSession)):
            row.absolute_expires_at = utc_now() - timedelta(seconds=1)
    sign_in(client)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(NativeSession)) == 1


def test_password_failure_does_not_revoke_or_modify(auth):  # type: ignore[no-untyped-def]
    client, factory, _ = auth
    token = sign_in(client)
    headers = {"Authorization": f"Bearer {token}"}
    with factory() as session:
        before = session.get(NativeCredential, LEGACY_USER_ID).password_hash
    assert (
        client.post(
            "/api/v1/auth/password",
            headers=headers,
            json={"current_password": "wrong", "new_password": "different-long-password"},
        ).status_code
        == 401
    )
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    with factory() as session:
        assert session.get(NativeCredential, LEGACY_USER_ID).password_hash == before


@pytest.mark.parametrize("encoded", ["invalid", "$argon2id$v=19$m=8192,t=1,p=1$c2FsdHNhbHQ$YWJj"])
def test_invalid_or_weak_credentials_fail_closed(auth, encoded):  # type: ignore[no-untyped-def]
    client, factory, _ = auth
    with factory.begin() as session:
        session.get(NativeCredential, LEGACY_USER_ID).password_hash = encoded
    assert (
        client.post("/api/v1/auth/login", json={"login": "owner", "password": PASSWORD}).status_code
        == 401
    )
    assert client.get("/api/v1/auth/health").status_code == 503


def test_enrollment_does_not_link_duplicate_email(auth, engine):  # type: ignore[no-untyped-def]
    _, factory, _ = auth
    second_id = uuid.uuid4()
    with factory.begin() as session:
        email = session.get(UserProfile, LEGACY_USER_ID).email
        session.add(UserProfile(id=second_id, auth_subject="other-external", email=email))
    with pytest.raises(AuthError, match="assigned"):
        native.enroll(factory, engine, second_id, "OWNER", PASSWORD)
    native.enroll(factory, engine, second_id, "other-owner", PASSWORD)
    with factory() as session:
        assert session.get(NativeCredential, second_id).login == "other-owner"
        assert session.get(NativeCredential, LEGACY_USER_ID).login == "owner"


def test_no_enrollment_is_not_ready(engine):  # type: ignore[no-untyped-def]
    settings = Settings(environment="test", auth_mode="native")
    with TestClient(create_app(settings, engine)) as client:
        assert client.get("/api/v1/auth/health").status_code == 503
        assert client.get("/health/ready").status_code == 503


def test_missing_origin_rejected(auth):  # type: ignore[no-untyped-def]
    client, _, _ = auth
    client.headers.pop("Origin")
    assert (
        client.post("/api/v1/auth/login", json={"login": "owner", "password": PASSWORD}).status_code
        == 403
    )


def test_auth_telemetry_is_dropped_and_query_scrubbed() -> None:
    from packages.observability.sentry import _scrub

    assert (
        _scrub({"request": {"url": "https://mil.test/api/v1/auth/login", "data": PASSWORD}}, {})
        is None
    )
    event = {
        "request": {
            "url": "https://mil.test/api/v1/assets?token=secret",
            "query_string": "token=secret",
            "headers": {"Authorization": "secret"},
        }
    }
    result = _scrub(event, {})
    assert "secret" not in str(result)
