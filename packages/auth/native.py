"""Local credentials and opaque sessions. No provider calls or browser cookies.

Transactions here are separate from application transactions. PostgreSQL advisory
locks bound hashing across processes; fixed-slot rate buckets bound cardinality.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta

from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import Engine, delete, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from packages.auth.service import AuthError, AuthPrincipal
from packages.core.config import Settings
from packages.core.time import utc_now
from packages.database.models import (
    AuthRateBucket,
    NativeCredential,
    NativeSession,
    UserProfile,
)
from packages.provenance import record_audit_event

# Deliberately not environment-overridable: test and production use the same floor.
HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1, type=Type.ID)
HASH_CONCURRENCY = 2
_HASH_GATE = threading.BoundedSemaphore(HASH_CONCURRENCY)
_DUMMY_HASH = HASHER.hash(secrets.token_urlsafe(32))
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}\Z")


class AuthBusy(AuthError):
    pass


def normalize_login(login: str) -> str:
    value = login.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9@._+\-]{2,159}", value):
        raise AuthError("Invalid credentials")
    return value


def validate_password(password: str) -> None:
    if not 15 <= len(password) <= 128:
        raise AuthError("Password must contain 15 to 128 characters")


@contextmanager
def hash_slot(engine: Engine) -> Iterator[None]:
    if not _HASH_GATE.acquire(blocking=False):
        raise AuthBusy("Authentication temporarily limited")
    try:
        if engine.dialect.name != "postgresql":
            yield
            return
        # Transaction-scoped locks release on connection loss or rollback. No leases
        # that can expire while a hash is still running. Namespace reserved for auth.
        with engine.connect() as connection, connection.begin():
            slot = next(
                (
                    i
                    for i in range(HASH_CONCURRENCY)
                    if connection.scalar(
                        text("SELECT pg_try_advisory_xact_lock(150200, :slot)"), {"slot": i}
                    )
                ),
                None,
            )
            if slot is None:
                raise AuthBusy("Authentication temporarily limited")
            yield
    finally:
        _HASH_GATE.release()


def password_matches(encoded: str, password: str) -> bool:
    try:
        if not hash_policy_valid(encoded):
            HASHER.verify(_DUMMY_HASH, password)
            return False
        return HASHER.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def hash_policy_valid(encoded: str) -> bool:
    try:
        parameters = extract_parameters(encoded)
    except InvalidHashError:
        return False
    return (
        parameters.type == Type.ID
        and parameters.version == 19
        and parameters.memory_cost == 65536
        and parameters.time_cost == 3
        and parameters.parallelism == 1
        and parameters.hash_len == 32
        and parameters.salt_len >= 16
    )


def audit(session: Session, action: str, user_id: uuid.UUID | None = None) -> None:
    session.info["actor_user_id"] = user_id
    record_audit_event(
        session,
        action=action,
        entity_type="authentication",
        entity_id=user_id or "unknown",
        result="failure" if action == "auth.sign_in_failed" else "success",
    )


def throttle(factory: sessionmaker[Session], settings: Settings, login: str, source: str) -> None:
    now = utc_now()

    # Collisions can conservatively throttle unrelated callers, never bypass a limit.
    def bucket(scope: str, value: str) -> str:
        index = int.from_bytes(hashlib.sha256(value.encode()).digest()[:4], "big") % 4096
        return f"{scope}:{index}"

    limits = [
        ("global", settings.auth_global_limit),
        (bucket("account", login), settings.auth_account_limit),
        (bucket("source", source), settings.auth_source_limit),
    ]
    with factory.begin() as session:
        insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert  # type: ignore[union-attr]
        # The upsert obtains the write lock on SQLite and serializes admissions on PG.
        session.execute(
            insert(AuthRateBucket)
            .values(key="global", attempts=0, expires_at=now + timedelta(seconds=60))
            .on_conflict_do_update(index_elements=["key"], set_={"key": "global"})
        )
        session.execute(
            delete(AuthRateBucket).where(
                AuthRateBucket.key != "global", AuthRateBucket.expires_at <= now
            )
        )
        rows = []
        for key, limit in limits:
            row = session.get(AuthRateBucket, key)
            if row is None:
                row = AuthRateBucket(key=key, attempts=0, expires_at=now + timedelta(seconds=60))
                session.add(row)
            elif row.expires_at <= now:
                row.attempts = 0
                row.expires_at = now + timedelta(seconds=60)
            rows.append((row, limit))
        limited = any(row.attempts >= limit for row, limit in rows)
        if not limited:
            for row, _ in rows:
                row.attempts += 1
    if limited:
        raise AuthBusy("Authentication temporarily limited")


def enroll(
    factory: sessionmaker[Session],
    engine: Engine,
    user_id: uuid.UUID,
    login: str,
    password: str,
    *,
    reset: bool = False,
) -> None:
    login = normalize_login(login)
    validate_password(password)
    with hash_slot(engine):
        encoded = HASHER.hash(password)
    with factory.begin() as session:
        profile = session.scalar(
            select(UserProfile).where(UserProfile.id == user_id).with_for_update()
        )
        if profile is None or profile.is_disabled:
            raise AuthError("Select an existing enabled profile")
        collision = session.scalar(select(NativeCredential).where(NativeCredential.login == login))
        if collision is not None and collision.user_id != user_id:
            raise AuthError("Login identifier is already assigned")
        credential = session.get(NativeCredential, user_id)
        if credential is not None and not reset:
            raise AuthError("Credential exists; explicit reset is required")
        if credential is None and reset:
            raise AuthError("Cannot reset an unenrolled profile")
        if credential is None:
            session.add(NativeCredential(user_id=user_id, login=login, password_hash=encoded))
        else:
            credential.login = login
            credential.password_hash = encoded
            credential.version += 1
            session.execute(
                update(NativeSession)
                .where(NativeSession.user_id == user_id, NativeSession.revoked_at.is_(None))
                .values(revoked_at=utc_now())
            )
            audit(session, "auth.sessions_revoked", user_id)
        audit(session, "auth.password_reset_completed" if reset else "auth.enrolled", user_id)


def login(
    factory: sessionmaker[Session],
    engine: Engine,
    settings: Settings,
    identifier: str,
    password: str,
    source: str,
) -> str:
    identifier = normalize_login(identifier)
    throttle(factory, settings, identifier, source)
    with factory() as session:
        credential = session.scalar(
            select(NativeCredential).where(NativeCredential.login == identifier)
        )
        encoded = credential.password_hash if credential else _DUMMY_HASH
        version = credential.version if credential else 0
        user_id = credential.user_id if credential else None
    with hash_slot(engine):
        valid = password_matches(encoded, password)
    with factory.begin() as session:
        # Serialize issuance with enrollment/reset/password change using the profile.
        profile = (
            session.scalar(select(UserProfile).where(UserProfile.id == user_id).with_for_update())
            if user_id
            else None
        )
        current = session.get(NativeCredential, user_id) if user_id else None
        if (
            not valid
            or profile is None
            or profile.is_disabled
            or current is None
            or (current.version != version)
        ):
            audit(session, "auth.sign_in_failed")
            failed = True
        else:
            failed = False
            now = utc_now()
            session.execute(delete(NativeSession).where(NativeSession.absolute_expires_at <= now))
            existing = session.scalars(
                select(NativeSession)
                .where(NativeSession.user_id == user_id)
                .order_by(NativeSession.issued_at.desc())
            ).all()
            for old in existing[9:]:
                session.delete(old)
            if len(existing) >= 10:
                audit(session, "auth.sessions_revoked", user_id)
            token = secrets.token_urlsafe(32)
            session.add(
                NativeSession(
                    token_digest=hashlib.sha256(token.encode()).hexdigest(),
                    user_id=user_id,
                    credential_version=version,
                    last_seen_at=now,
                    idle_expires_at=now + timedelta(seconds=settings.auth_idle_seconds),
                    absolute_expires_at=now + timedelta(seconds=settings.auth_absolute_seconds),
                )
            )
            audit(session, "auth.sign_in_succeeded", user_id)
    if failed:
        raise AuthError("Invalid credentials")
    return token


def authenticate(
    factory: sessionmaker[Session],
    settings: Settings,
    authorization: str | None,
) -> AuthPrincipal:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not _TOKEN.fullmatch(token):
        raise AuthError("Invalid or expired session")
    now = utc_now()
    with factory.begin() as session:
        row = session.execute(
            select(NativeSession, NativeCredential, UserProfile)
            .join(NativeCredential, NativeCredential.user_id == NativeSession.user_id)
            .join(UserProfile, UserProfile.id == NativeSession.user_id)
            .where(NativeSession.token_digest == hashlib.sha256(token.encode()).hexdigest())
        ).first()
        if row is None:
            raise AuthError("Invalid or expired session")
        active, credential, profile = row
        if (
            active.revoked_at is not None
            or active.idle_expires_at <= now
            or active.absolute_expires_at <= now
            or credential.version != active.credential_version
            or profile.is_disabled
        ):
            raise AuthError("Invalid or expired session")
        if active.last_seen_at <= now - timedelta(seconds=settings.auth_touch_seconds):
            session.execute(
                update(NativeSession)
                .where(
                    NativeSession.id == active.id,
                    NativeSession.last_seen_at == active.last_seen_at,
                    NativeSession.revoked_at.is_(None),
                    NativeSession.idle_expires_at > now,
                )
                .values(
                    last_seen_at=now,
                    idle_expires_at=min(
                        now + timedelta(seconds=settings.auth_idle_seconds),
                        active.absolute_expires_at,
                    ),
                )
            )
        return AuthPrincipal(
            profile.id,
            profile.auth_subject,
            profile.email,
            profile.email_verified,
            str(active.id),
            "native",
        )


def logout(factory: sessionmaker[Session], principal: AuthPrincipal) -> None:
    with factory.begin() as session:
        session.execute(
            update(NativeSession)
            .where(
                NativeSession.id == uuid.UUID(str(principal.session_id)),
                NativeSession.user_id == principal.user_id,
            )
            .values(revoked_at=utc_now())
        )
        audit(session, "auth.signed_out", principal.user_id)


def change_password(
    factory: sessionmaker[Session],
    engine: Engine,
    settings: Settings,
    principal: AuthPrincipal,
    current_password: str,
    new_password: str,
    source: str,
) -> None:
    validate_password(new_password)
    with factory() as session:
        credential = session.get(NativeCredential, principal.user_id)
        if credential is None:
            raise AuthError("Invalid credentials")
        identifier, encoded, version = (
            credential.login,
            credential.password_hash,
            credential.version,
        )
    throttle(factory, settings, identifier, source)
    with hash_slot(engine):
        if not password_matches(encoded, current_password):
            with factory.begin() as session:
                audit(session, "auth.sign_in_failed", principal.user_id)
            raise AuthError("Invalid credentials")
        replacement = HASHER.hash(new_password)
    with factory.begin() as session:
        profile = session.scalar(
            select(UserProfile).where(UserProfile.id == principal.user_id).with_for_update()
        )
        credential = session.get(NativeCredential, principal.user_id)
        active = session.get(NativeSession, uuid.UUID(str(principal.session_id)))
        now = utc_now()
        if (
            profile is None
            or profile.is_disabled
            or credential is None
            or credential.version != version
            or active is None
            or active.revoked_at
            or active.credential_version != version
            or active.idle_expires_at <= now
            or active.absolute_expires_at <= now
        ):
            raise AuthError("Invalid or expired session")
        credential.password_hash = replacement
        credential.version += 1
        session.execute(
            update(NativeSession)
            .where(NativeSession.user_id == principal.user_id, NativeSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        audit(session, "auth.password_changed", principal.user_id)
        audit(session, "auth.sessions_revoked", principal.user_id)


def ready(session: Session) -> bool:
    # Probe every auth table and require at least one enabled enrolled identity.
    session.execute(select(NativeSession.id).limit(1))
    session.execute(select(AuthRateBucket.key).limit(1))
    encoded = session.scalar(
        select(NativeCredential.password_hash)
        .join(UserProfile)
        .where(UserProfile.is_disabled.is_(False))
        .limit(1)
    )
    return encoded is not None and hash_policy_valid(encoded)
