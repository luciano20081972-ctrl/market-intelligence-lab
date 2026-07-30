from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db, get_principal
from packages.auth import AuthError, AuthPrincipal, authenticate_request
from packages.core.time import utc_now
from packages.database.models import (
    AuditEvent,
    UserProfile,
    Workspace,
    WorkspaceInvitation,
    WorkspaceMembership,
)
from packages.provenance import record_audit_event
from packages.security import WorkspaceContext

router = APIRouter(tags=["identity and workspaces"])
Role = Literal["owner", "admin", "member", "viewer"]


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)


class WorkspaceUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class InvitationCreate(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=320)
    role: Literal["admin", "member", "viewer"] = "member"


class MembershipUpdate(BaseModel):
    role: Role


class AuthAuditPayload(BaseModel):
    action: Literal[
        "auth.sign_in_succeeded",
        "auth.sign_in_failed",
        "auth.signed_out",
        "auth.password_reset_requested",
        "auth.password_reset_completed",
    ]
    result: Literal["success", "failure"]


def _profile(session: Session, principal: AuthPrincipal) -> UserProfile:
    profile = session.get(UserProfile, principal.user_id)
    if profile is None:
        raise HTTPException(status_code=401, detail="Authenticated profile is unavailable")
    return profile


def _membership(
    session: Session, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> WorkspaceMembership:
    membership = session.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Workspace was not found")
    return membership


def _require_workspace_permission(
    session: Session, workspace_id: uuid.UUID, user_id: uuid.UUID, permission: str
) -> WorkspaceContext:
    membership = _membership(session, workspace_id, user_id)
    context = WorkspaceContext(workspace_id, user_id, membership.role)
    if not context.allows(permission):
        raise HTTPException(status_code=403, detail="Permission denied")
    session.info["workspace_id"] = workspace_id
    return context


def _workspace_response(workspace: Workspace, role: str) -> dict[str, object]:
    return {
        "id": workspace.id,
        "name": workspace.name,
        "slug": workspace.slug,
        "role": role,
        "created_at": workspace.created_at,
        "updated_at": workspace.updated_at,
    }


@router.get("/auth/me")
def auth_me(
    principal: AuthPrincipal = Depends(get_principal), session: Session = Depends(get_db)
) -> dict[str, object]:
    profile = _profile(session, principal)
    return {
        "id": profile.id,
        "email": profile.email,
        "email_verified": profile.email_verified,
        "display_name": profile.display_name,
        "provider": principal.provider,
    }


@router.get("/auth/health")
def auth_health(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    return {
        "status": "healthy"
        if settings.auth_mode == "disabled" or settings.supabase_url
        else "unconfigured",
        "mode": settings.auth_mode,
        "provider_configured": settings.auth_mode == "disabled" or bool(settings.supabase_url),
    }


@router.post("/auth/events", status_code=202)
def record_auth_event(
    payload: AuthAuditPayload, request: Request, session: Session = Depends(get_db)
) -> dict[str, bool]:
    try:
        principal = authenticate_request(
            request.app.state.settings, request.headers.get("Authorization")
        )
    except AuthError:
        principal = None
    if principal is not None:
        if session.get(UserProfile, principal.user_id) is None:
            session.add(
                UserProfile(
                    id=principal.user_id,
                    auth_subject=principal.subject,
                    email=principal.email,
                    email_verified=principal.email_verified,
                )
            )
            session.flush()
        session.info["actor_user_id"] = principal.user_id
        membership = session.scalar(
            select(WorkspaceMembership)
            .where(WorkspaceMembership.user_id == principal.user_id)
            .order_by(WorkspaceMembership.created_at)
        )
        if membership is not None:
            session.info["workspace_id"] = membership.workspace_id
    record_audit_event(
        session,
        action=payload.action,
        entity_type="authentication",
        entity_id=str(principal.user_id) if principal else "anonymous",
        result=payload.result,
    )
    session.commit()
    return {"recorded": True}


@router.get("/users/me")
def get_user_me(
    principal: AuthPrincipal = Depends(get_principal), session: Session = Depends(get_db)
) -> dict[str, object]:
    return auth_me(principal, session)


@router.patch("/users/me")
def update_user_me(
    payload: ProfileUpdate,
    principal: AuthPrincipal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    profile = _profile(session, principal)
    profile.display_name = payload.display_name.strip()
    profile.updated_at = utc_now()
    session.commit()
    return auth_me(principal, session)


@router.post("/workspaces", status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    principal: AuthPrincipal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    workspace = Workspace(
        name=payload.name.strip(), slug=payload.slug, created_by_user_id=principal.user_id
    )
    session.add(workspace)
    session.flush()
    membership = WorkspaceMembership(
        workspace_id=workspace.id, user_id=principal.user_id, role="owner"
    )
    session.add(membership)
    session.info["workspace_id"] = workspace.id
    record_audit_event(
        session, action="workspace.created", entity_type="workspace", entity_id=workspace.id
    )
    session.commit()
    return _workspace_response(workspace, membership.role)


@router.get("/workspaces")
def list_workspaces(
    principal: AuthPrincipal = Depends(get_principal), session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    rows = session.execute(
        select(Workspace, WorkspaceMembership.role)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .where(WorkspaceMembership.user_id == principal.user_id)
        .order_by(Workspace.name)
    ).all()
    return [_workspace_response(workspace, role) for workspace, role in rows]


@router.get("/workspaces/{workspace_id}")
def get_workspace(
    workspace_id: uuid.UUID,
    principal: AuthPrincipal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    membership = _membership(session, workspace_id, principal.user_id)
    workspace = session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace was not found")
    return _workspace_response(workspace, membership.role)


@router.patch("/workspaces/{workspace_id}")
def update_workspace(
    workspace_id: uuid.UUID,
    payload: WorkspaceUpdate,
    principal: AuthPrincipal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    context = _require_workspace_permission(
        session, workspace_id, principal.user_id, "workspace.update"
    )
    workspace = session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace was not found")
    workspace.name = payload.name.strip()
    workspace.updated_at = utc_now()
    record_audit_event(
        session, action="workspace.updated", entity_type="workspace", entity_id=workspace.id
    )
    session.commit()
    return _workspace_response(workspace, context.role)


@router.get("/workspaces/{workspace_id}/members")
def list_members(
    workspace_id: uuid.UUID,
    principal: AuthPrincipal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> list[dict[str, object]]:
    _require_workspace_permission(session, workspace_id, principal.user_id, "workspace.read")
    rows = session.execute(
        select(WorkspaceMembership, UserProfile)
        .join(UserProfile, UserProfile.id == WorkspaceMembership.user_id)
        .where(WorkspaceMembership.workspace_id == workspace_id)
        .order_by(UserProfile.email)
    ).all()
    return [
        {
            "id": membership.id,
            "user_id": profile.id,
            "email": profile.email,
            "display_name": profile.display_name,
            "role": membership.role,
        }
        for membership, profile in rows
    ]


@router.post("/workspaces/{workspace_id}/invitations", status_code=201)
def create_invitation(
    workspace_id: uuid.UUID,
    payload: InvitationCreate,
    principal: AuthPrincipal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    _require_workspace_permission(session, workspace_id, principal.user_id, "members.manage")
    token_digest = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    invitation = WorkspaceInvitation(
        workspace_id=workspace_id,
        email=str(payload.email).lower(),
        role=payload.role,
        token_digest=token_digest,
        invited_by_user_id=principal.user_id,
        expires_at=utc_now() + timedelta(days=7),
    )
    session.add(invitation)
    session.flush()
    record_audit_event(
        session,
        action="workspace.invitation_created",
        entity_type="workspace_invitation",
        entity_id=invitation.id,
        details={"role": invitation.role},
    )
    session.commit()
    return {"id": invitation.id, "email": invitation.email, "role": invitation.role}


@router.patch("/workspaces/{workspace_id}/members/{member_id}")
def update_member(
    workspace_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: MembershipUpdate,
    principal: AuthPrincipal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    _require_workspace_permission(session, workspace_id, principal.user_id, "members.manage")
    membership = session.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.id == member_id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Member was not found")
    if membership.role == "owner" and payload.role != "owner":
        owners = session.scalar(
            select(func.count())
            .select_from(WorkspaceMembership)
            .where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.role == "owner",
            )
        )
        if owners == 1:
            raise HTTPException(status_code=409, detail="A workspace must retain an owner")
    membership.role = payload.role
    record_audit_event(
        session,
        action="workspace.member_role_changed",
        entity_type="workspace_membership",
        entity_id=membership.id,
        details={"role": payload.role},
    )
    session.commit()
    return {"id": membership.id, "user_id": membership.user_id, "role": membership.role}


@router.delete("/workspaces/{workspace_id}/members/{member_id}", status_code=204)
def delete_member(
    workspace_id: uuid.UUID,
    member_id: uuid.UUID,
    principal: AuthPrincipal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> None:
    _require_workspace_permission(session, workspace_id, principal.user_id, "members.manage")
    membership = session.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.id == member_id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Member was not found")
    if membership.role == "owner":
        raise HTTPException(status_code=409, detail="Owners must transfer ownership first")
    session.delete(membership)
    record_audit_event(
        session,
        action="workspace.member_removed",
        entity_type="workspace_membership",
        entity_id=membership.id,
    )
    session.commit()


@router.get("/workspaces/{workspace_id}/audit-events")
def list_audit_events(
    workspace_id: uuid.UUID,
    principal: AuthPrincipal = Depends(get_principal),
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> dict[str, object]:
    _require_workspace_permission(session, workspace_id, principal.user_id, "audit.read")
    total = (
        session.scalar(
            select(func.count(AuditEvent.id)).where(AuditEvent.workspace_id == workspace_id)
        )
        or 0
    )
    events = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.workspace_id == workspace_id)
        .order_by(AuditEvent.occurred_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [
            {
                "id": event.id,
                "timestamp": event.occurred_at,
                "actor_user_id": event.actor_user_id,
                "workspace_id": event.workspace_id,
                "action": event.action,
                "resource_type": event.entity_type,
                "resource_id": event.entity_id,
                "result": event.result,
                "metadata": event.details,
                "correlation_id": event.correlation_id,
            }
            for event in events
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }
