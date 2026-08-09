from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.core.time import utc_now
from packages.database.models import AlertEvent


@dataclass(frozen=True)
class AlertCandidate:
    workspace_id: UUID
    category: str
    severity: str
    dedupe_key: str
    title: str
    message: str
    payload: dict[str, Any]
    cooldown_seconds: int = 900


class AlertChannel(Protocol):
    name: str

    def deliver(self, session: Session, candidate: AlertCandidate) -> tuple[AlertEvent, bool]: ...


class InAppAlertChannel:
    name = "in_app"

    def deliver(self, session: Session, candidate: AlertCandidate) -> tuple[AlertEvent, bool]:
        return create_or_deduplicate_alert(session, candidate)


def create_or_deduplicate_alert(
    session: Session, candidate: AlertCandidate
) -> tuple[AlertEvent, bool]:
    existing = session.scalar(
        select(AlertEvent).where(
            AlertEvent.workspace_id == candidate.workspace_id,
            AlertEvent.dedupe_key == candidate.dedupe_key,
        )
    )
    now = utc_now()
    if existing is not None:
        existing.occurrence_count += 1
        existing.last_seen_at = now
        existing.payload = candidate.payload
        if existing.cooldown_until is None or now >= existing.cooldown_until:
            existing.cooldown_until = now + timedelta(seconds=candidate.cooldown_seconds)
        return existing, False
    alert = AlertEvent(
        workspace_id=candidate.workspace_id,
        category=candidate.category,
        severity=candidate.severity,
        dedupe_key=candidate.dedupe_key,
        title=candidate.title,
        message=candidate.message,
        payload=candidate.payload,
        channel="in_app",
        status="ACTIVE",
        occurrence_count=1,
        cooldown_until=now + timedelta(seconds=candidate.cooldown_seconds),
        last_seen_at=now,
    )
    session.add(alert)
    session.flush()
    return alert, True
