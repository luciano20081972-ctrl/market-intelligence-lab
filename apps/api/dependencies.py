from collections.abc import Callable, Iterator
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from packages.auth import AuthError, AuthPrincipal, authenticate_request
from packages.auth.bootstrap import ensure_legacy_workspace
from packages.database.models import UserProfile, WorkspaceMembership
from packages.security import WorkspaceContext
from packages.security.authorization import permission_for_request


def get_db(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_principal(request: Request, session: Session = Depends(get_db)) -> AuthPrincipal:
    try:
        principal = authenticate_request(
            request.app.state.settings, request.headers.get("Authorization")
        )
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "authentication_failed", "message": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if request.app.state.settings.auth_mode == "disabled":
        ensure_legacy_workspace(session)
    profile = session.get(UserProfile, principal.user_id)
    if profile is None:
        profile = UserProfile(
            id=principal.user_id,
            auth_subject=principal.subject,
            email=principal.email,
            email_verified=principal.email_verified,
        )
        session.add(profile)
        session.flush()
    elif profile.is_disabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "user_disabled", "message": "This user account is disabled"},
        )
    session.info["actor_user_id"] = principal.user_id
    session.info["correlation_id"] = getattr(request.state, "correlation_id", None)
    session.info["user_agent_summary"] = request.headers.get("User-Agent", "")[:160] or None
    return principal


def get_workspace_context(
    request: Request,
    principal: AuthPrincipal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> WorkspaceContext:
    memberships = session.query(WorkspaceMembership).filter_by(user_id=principal.user_id).all()
    requested = request.headers.get("X-Workspace-ID")
    try:
        requested_id = UUID(requested) if requested else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="X-Workspace-ID is not a valid UUID") from exc
    membership = next(
        (item for item in memberships if requested_id is None or item.workspace_id == requested_id),
        None,
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Workspace was not found")
    context = WorkspaceContext(
        workspace_id=membership.workspace_id,
        user_id=principal.user_id,
        role=membership.role,
    )
    session.info["workspace_id"] = context.workspace_id
    session.info["workspace_role"] = context.role
    permission = permission_for_request(request.method, request.url.path)
    if not context.allows(permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "permission_denied", "message": "Permission denied"},
        )
    return context


def require_permission(permission: str) -> Callable[..., WorkspaceContext]:
    def dependency(context: WorkspaceContext = Depends(get_workspace_context)) -> WorkspaceContext:
        if not context.allows(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "permission_denied", "message": "Permission denied"},
            )
        return context

    return dependency
