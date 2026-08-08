from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from packages.database.models import (
    AnalyticsComparisonRecord,
    BacktestRun,
    CompanyDriverEntry,
    CompanyDriverProfile,
    DataRelevanceDecision,
    EconomicEntity,
    EconomicRelationship,
    EntityAlias,
    EntityIdentifier,
    EntityResolutionCandidate,
    EntityResolutionDecision,
    EvidenceRecord,
    ExternalEngineRun,
    GraphQualityIssue,
    GraphRecomputeJob,
    ImportJob,
    ImportSchedule,
    OptimizationExperiment,
    PaperPortfolio,
    ProviderComparison,
    RelationshipConfidenceComponent,
    RelationshipEvidence,
    SecIngestionJob,
    Strategy,
    Watchlist,
)

WORKSPACE_MODELS = (
    Watchlist,
    Strategy,
    BacktestRun,
    PaperPortfolio,
    ImportJob,
    ImportSchedule,
    ProviderComparison,
    AnalyticsComparisonRecord,
    OptimizationExperiment,
    ExternalEngineRun,
    SecIngestionJob,
    EconomicEntity,
    EntityIdentifier,
    EntityAlias,
    EntityResolutionCandidate,
    EntityResolutionDecision,
    EconomicRelationship,
    EvidenceRecord,
    RelationshipEvidence,
    RelationshipConfidenceComponent,
    CompanyDriverProfile,
    CompanyDriverEntry,
    DataRelevanceDecision,
    GraphQualityIssue,
    GraphRecomputeJob,
)


def install_workspace_guards() -> None:
    if getattr(Session, "_mil_workspace_guards", False):
        return

    @event.listens_for(Session, "do_orm_execute")
    def _scope_reads(execute_state: object) -> None:
        if not getattr(execute_state, "is_select", False):
            return
        session = execute_state.session  # type: ignore[attr-defined]
        workspace_id = session.info.get("workspace_id")
        if workspace_id is None or session.info.get("bypass_workspace_scope"):
            return
        statement = execute_state.statement  # type: ignore[attr-defined]
        for model in WORKSPACE_MODELS:
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
        if workspace_id is None:
            return
        for value in session.new:
            if isinstance(value, WORKSPACE_MODELS):
                current = getattr(value, "workspace_id", None)
                if current is None:
                    value.workspace_id = workspace_id
                elif current != workspace_id and not session.info.get("bypass_workspace_scope"):
                    raise PermissionError("Cross-workspace write was blocked")

    Session._mil_workspace_guards = True  # type: ignore[attr-defined]
