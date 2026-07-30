from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database.models import (
    LEGACY_USER_ID,
    LEGACY_WORKSPACE_ID,
    UserProfile,
    Workspace,
    WorkspaceMembership,
)


def ensure_legacy_workspace(session: Session) -> None:
    """Provision the deterministic owner/workspace used by local and migrated demo data."""

    if session.get(UserProfile, LEGACY_USER_ID) is None:
        session.add(
            UserProfile(
                id=LEGACY_USER_ID,
                auth_subject="development-user",
                email="developer@localhost.invalid",
                display_name="Local Developer",
                email_verified=True,
            )
        )
        session.flush()
    if session.get(Workspace, LEGACY_WORKSPACE_ID) is None:
        session.add(
            Workspace(
                id=LEGACY_WORKSPACE_ID,
                name="Legacy Development Workspace",
                slug="legacy-development",
                created_by_user_id=LEGACY_USER_ID,
            )
        )
        session.flush()
    membership = session.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == LEGACY_WORKSPACE_ID,
            WorkspaceMembership.user_id == LEGACY_USER_ID,
        )
    )
    if membership is None:
        session.add(
            WorkspaceMembership(
                workspace_id=LEGACY_WORKSPACE_ID,
                user_id=LEGACY_USER_ID,
                role="owner",
            )
        )
        session.flush()
