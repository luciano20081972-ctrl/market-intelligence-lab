from __future__ import annotations

import argparse
import sys
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from packages.core.config import get_settings
from packages.database.models import AuditEvent, UserProfile, Workspace, WorkspaceMembership
from packages.provenance import record_audit_event


def provision_owner(
    session: Session,
    *,
    email: str,
    subject: str,
    workspace_slug: str,
    profile_id: uuid.UUID,
    apply: bool,
) -> dict[str, object]:
    normalized_email = email.strip().lower()
    try:
        uuid.UUID(subject)
    except ValueError as exc:
        raise ValueError("Supabase subject must be a UUID") from exc
    workspace = session.scalar(select(Workspace).where(Workspace.slug == workspace_slug))
    profile = session.get(UserProfile, profile_id)
    if workspace is None or profile is None:
        raise ValueError("Existing workspace and profile must both match exactly")
    membership = session.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace.id,
            WorkspaceMembership.user_id == profile.id,
        )
    )
    if membership is None or membership.role != "owner":
        raise ValueError("Existing owner membership is required; recovery never creates one")
    collisions = session.scalars(
        select(UserProfile).where(
            UserProfile.id != profile.id,
            (UserProfile.auth_subject == subject) | (UserProfile.email == normalized_email),
        )
    ).all()
    if collisions:
        raise ValueError("Subject or email already belongs to another profile")
    changes = []
    if profile.auth_subject != subject:
        changes.append("link Supabase subject")
    if profile.email != normalized_email:
        changes.append("update owner email")
    if not profile.email_verified:
        changes.append("mark confirmed email")
    result: dict[str, object] = {
        "mode": "apply" if apply else "dry-run",
        "profile_id": str(profile.id),
        "workspace_id": str(workspace.id),
        "workspace_slug": workspace.slug,
        "changes": changes,
        "creates_profile": False,
        "creates_workspace": False,
        "creates_membership": False,
    }
    if not apply or not changes:
        return result
    profile.auth_subject = subject
    profile.email = normalized_email
    profile.email_verified = True
    session.info["actor_user_id"] = profile.id
    session.info["workspace_id"] = workspace.id
    prior = session.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "auth.owner_provisioned",
            AuditEvent.entity_id == str(profile.id),
        )
    )
    if prior is None:
        record_audit_event(
            session,
            action="auth.owner_provisioned",
            entity_type="user_profile",
            entity_id=profile.id,
            details={"workspace_slug": workspace.slug, "changes": changes},
        )
    session.commit()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Link an existing owner to a Supabase identity")
    parser.add_argument("--email", required=True)
    parser.add_argument("--subject", required=True, help="Supabase Auth user UUID")
    parser.add_argument("--workspace-slug", required=True)
    parser.add_argument("--profile-id", required=True, type=uuid.UUID)
    parser.add_argument("--apply", action="store_true", help="Apply after backup and approval")
    args = parser.parse_args()
    try:
        with Session(create_engine(get_settings().database_url)) as session:
            result = provision_owner(
                session,
                email=args.email,
                subject=args.subject,
                workspace_slug=args.workspace_slug,
                profile_id=args.profile_id,
                apply=args.apply,
            )
            print(result)
    except (ValueError, TypeError) as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
