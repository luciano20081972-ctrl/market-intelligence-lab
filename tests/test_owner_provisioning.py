import uuid

from sqlalchemy import select

from packages.database.models import (
    LEGACY_USER_ID,
    LEGACY_WORKSPACE_ID,
    AuditEvent,
    UserProfile,
    WorkspaceMembership,
)
from packages.database.session import make_session_factory, session_scope
from scripts.provision_owner import provision_owner


def test_owner_provisioning_is_dry_run_then_idempotent(engine: object) -> None:
    subject = str(uuid.uuid4())
    factory = make_session_factory(engine)  # type: ignore[arg-type]
    with session_scope(factory) as session:
        dry_run = provision_owner(
            session,
            email="owner@example.test",
            subject=subject,
            workspace_slug="legacy-development",
            profile_id=LEGACY_USER_ID,
            apply=False,
        )
        assert dry_run.startswith("Dry run:")
        assert session.get(UserProfile, LEGACY_USER_ID).auth_subject == "development-user"

    with session_scope(factory) as session:
        result = provision_owner(
            session,
            email="owner@example.test",
            subject=subject,
            workspace_slug="legacy-development",
            profile_id=LEGACY_USER_ID,
            apply=True,
        )
        assert result.startswith("Applied:")

    with session_scope(factory) as session:
        profile = session.get(UserProfile, LEGACY_USER_ID)
        assert profile is not None
        assert profile.auth_subject == subject
        assert profile.email == "owner@example.test"
        membership = session.scalar(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == LEGACY_WORKSPACE_ID,
                WorkspaceMembership.user_id == LEGACY_USER_ID,
            )
        )
        assert membership is not None and membership.role == "owner"
        assert session.scalar(
            select(AuditEvent).where(AuditEvent.action == "auth.owner_provisioned")
        ) is not None
        assert provision_owner(
            session,
            email="owner@example.test",
            subject=subject,
            workspace_slug="legacy-development",
            profile_id=LEGACY_USER_ID,
            apply=False,
        ) == "Dry run: already provisioned"
