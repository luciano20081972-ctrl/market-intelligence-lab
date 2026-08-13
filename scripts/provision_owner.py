from __future__ import annotations

import argparse
import sys
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from packages.core.config import get_settings
from packages.database.models import UserProfile, Workspace, WorkspaceMembership
from packages.provenance import record_audit_event


def provision_owner(
    session: Session,
    *,
    email: str,
    subject: str,
    workspace_slug: str,
    profile_id: uuid.UUID | None,
    apply: bool,
) -> str:
    normalized_email = email.strip().lower()
    try:
        uuid.UUID(subject)
    except ValueError as exc:
        raise ValueError("Supabase subject must be a UUID") from exc

    workspaces = session.scalars(
        select(Workspace).where(Workspace.slug == workspace_slug)
    ).all()
    if len(workspaces) != 1:
        raise ValueError("Workspace slug must match exactly one existing workspace")
    workspace = workspaces[0]

    if profile_id is not None:
        explicit = session.get(UserProfile, profile_id)
        candidates = {explicit.id: explicit} if explicit is not None else {}
    else:
        subject_matches = session.scalars(
            select(UserProfile).where(UserProfile.auth_subject == subject)
        ).all()
        email_matches = session.scalars(
            select(UserProfile).where(UserProfile.email == normalized_email)
        ).all()
        candidates = {profile.id: profile for profile in [*subject_matches, *email_matches]}
    if len(candidates) != 1:
        raise ValueError("Owner identity must match exactly one existing application profile")
    profile = next(iter(candidates.values()))
    membership = session.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace.id,
            WorkspaceMembership.user_id == profile.id,
        )
    )
    changes: list[str] = []
    if profile.auth_subject != subject:
        changes.append("link Supabase subject")
    if profile.email != normalized_email:
        changes.append("update owner email")
    if not profile.email_verified:
        changes.append("mark confirmed email")
    if membership is None:
        changes.append("create owner membership")
    elif membership.role != "owner":
        changes.append("promote membership to owner")

    summary = ", ".join(changes) if changes else "already provisioned"
    if not apply:
        return f"Dry run: {summary}"

    profile.auth_subject = subject
    profile.email = normalized_email
    profile.email_verified = True
    if membership is None:
        membership = WorkspaceMembership(
            workspace_id=workspace.id, user_id=profile.id, role="owner"
        )
        session.add(membership)
    elif membership.role != "owner":
        membership.role = "owner"
    session.info["actor_user_id"] = profile.id
    session.info["workspace_id"] = workspace.id
    record_audit_event(
        session,
        action="auth.owner_provisioned",
        entity_type="user_profile",
        entity_id=profile.id,
        details={"workspace_slug": workspace.slug, "changes": changes},
    )
    session.commit()
    return f"Applied: {summary}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Link a Supabase owner to an existing workspace")
    parser.add_argument("--email", required=True)
    parser.add_argument("--subject", required=True, help="Supabase Auth user UUID")
    parser.add_argument("--workspace-slug", required=True)
    parser.add_argument(
        "--profile-id", type=uuid.UUID, help="Exact existing application profile UUID"
    )
    parser.add_argument("--apply", action="store_true", help="Apply changes; default is dry-run")
    args = parser.parse_args()
    try:
        with Session(create_engine(get_settings().database_url)) as session:
            print(provision_owner(
                session,
                email=args.email,
                subject=args.subject,
                workspace_slug=args.workspace_slug,
                profile_id=args.profile_id,
                apply=args.apply,
            ))
    except ValueError as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
