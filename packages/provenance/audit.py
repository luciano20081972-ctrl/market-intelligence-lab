from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from packages.database.models import AuditEvent


def record_audit_event(
    session: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: UUID | str,
    details: dict[str, Any] | None = None,
    result: str = "success",
) -> AuditEvent:
    event = AuditEvent(
        actor_user_id=session.info.get("actor_user_id"),
        workspace_id=session.info.get("workspace_id"),
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        details=details or {},
        result=result,
        correlation_id=session.info.get("correlation_id"),
        user_agent_summary=session.info.get("user_agent_summary"),
    )
    session.add(event)
    return event
