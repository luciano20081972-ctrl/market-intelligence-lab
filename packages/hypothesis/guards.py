from __future__ import annotations

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from packages.database.models import FactorExperiment


def install_hypothesis_guards() -> None:
    if getattr(Session, "_mil_hypothesis_guards", False):
        return

    @event.listens_for(Session, "before_flush")
    def _protect_completed_experiments(
        session: Session, _flush_context: object, _instances: object
    ) -> None:
        for value in session.dirty:
            if not isinstance(value, FactorExperiment):
                continue
            state = inspect(value)
            status_history = state.attrs.status.history
            was_terminal = (
                not status_history.has_changes() and value.status in {"COMPLETED", "REJECTED"}
            ) or any(status in {"COMPLETED", "REJECTED"} for status in status_history.deleted)
            if was_terminal:
                raise ValueError("completed experiments are immutable")

    Session._mil_hypothesis_guards = True  # type: ignore[attr-defined]
