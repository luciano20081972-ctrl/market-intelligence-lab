from __future__ import annotations

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session, with_loader_criteria

from packages.database import models as _models  # noqa: F401 -- load all resource mappings
from packages.database.base import Base


# Derive coverage from the schema rather than a hand-maintained allowlist.
# Nullable workspace IDs represent trusted system work, not tenant-wide access.
def workspace_models() -> tuple[type[Base], ...]:
    # Refresh from the registry so models imported after app creation cannot escape.
    models = tuple(
        mapper.class_
        for mapper in sorted(Base.registry.mappers, key=lambda item: item.class_.__name__)
        if "workspace_id" in mapper.persist_selectable.c
    )
    if not models:
        raise RuntimeError("Workspace model metadata is unavailable")
    return models


def install_workspace_guards() -> None:
    if getattr(Session, "_mil_workspace_guards", False):
        return

    @event.listens_for(Session, "do_orm_execute")
    def _scope_reads(execute_state: object) -> None:
        if not any(
            getattr(execute_state, kind, False) for kind in ("is_select", "is_update", "is_delete")
        ):
            return
        session = execute_state.session  # type: ignore[attr-defined]
        workspace_id = session.info.get("workspace_id")
        if workspace_id is None or session.info.get("bypass_workspace_scope"):
            return
        statement = execute_state.statement  # type: ignore[attr-defined]
        for model in workspace_models():
            statement = statement.options(
                with_loader_criteria(
                    model,
                    lambda cls: cls.workspace_id == workspace_id,
                    include_aliases=True,
                )
            )
        execute_state.statement = statement  # type: ignore[attr-defined]

    @event.listens_for(Session, "before_flush")
    def _scope_writes(session: Session, _flush_context: object, _instances: object) -> None:
        workspace_id = session.info.get("workspace_id")
        if workspace_id is None or session.info.get("bypass_workspace_scope"):
            return
        models = workspace_models()
        for value in session.new | session.dirty | session.deleted:
            if isinstance(value, models):
                current = getattr(value, "workspace_id", None)
                if current is None and value in session.new:
                    value.workspace_id = workspace_id  # type: ignore[attr-defined]
                elif current != workspace_id:
                    raise PermissionError("Cross-workspace write was blocked")
                history = inspect(value).attrs.workspace_id.history
                if history.deleted and any(old != workspace_id for old in history.deleted):
                    raise PermissionError("Workspace reassignment was blocked")

    Session._mil_workspace_guards = True  # type: ignore[attr-defined]
