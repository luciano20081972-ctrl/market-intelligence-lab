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
) -> AuditEvent:
    event = AuditEvent(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        details=details or {},
    )
    session.add(event)
    return event
