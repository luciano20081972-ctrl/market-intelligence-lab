from __future__ import annotations

import uuid
from dataclasses import dataclass

PERMISSIONS: dict[str, frozenset[str]] = {
    "owner": frozenset({"*"}),
    "admin": frozenset(
        {
            "workspace.read",
            "workspace.update",
            "members.manage",
            "audit.read",
            "research.write",
            "backtests.run",
            "paper.manage",
            "orders.submit",
            "schedules.manage",
            "providers.read",
            "providers.manage",
            "recovery.manage",
            "graph.manage",
        }
    ),
    "member": frozenset(
        {
            "workspace.read",
            "research.write",
            "backtests.run",
            "paper.manage",
            "orders.submit",
            "schedules.manage",
            "providers.read",
        }
    ),
    "viewer": frozenset({"workspace.read", "providers.read"}),
}


@dataclass(frozen=True)
class WorkspaceContext:
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    role: str

    def allows(self, permission: str) -> bool:
        granted = PERMISSIONS.get(self.role, frozenset())
        return "*" in granted or permission in granted


def permission_for_request(method: str, path: str) -> str:
    if method == "GET":
        return "workspace.read"
    if "/paper-portfolios/" in path and "/orders" in path:
        return "orders.submit"
    if "/paper-portfolios" in path:
        return "paper.manage"
    if "/backtests" in path:
        return "backtests.run"
    if "/watchlists" in path or "/strategies" in path:
        return "research.write"
    if "/schedules" in path or "/imports" in path:
        return "schedules.manage"
    if "/providers" in path or "/reconciliation" in path:
        return "providers.manage"
    if any(
        segment in path
        for segment in ("/sec/imports", "/analytics", "/optimization", "/upstream/engines")
    ):
        return "research.write"
    if any(
        segment in path
        for segment in ("/research/", "/feature", "/hypotheses", "/factor-experiments")
    ):
        return "research.write"
    if "/entity-resolution/" in path:
        return "graph.manage"
    return "workspace.read"
