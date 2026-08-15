from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db
from packages.database.models import (
    DivergenceDefinition,
    DivergenceEvent,
    EconomicEntity,
    FactorCluster,
    FactorRedundancyResult,
    HypothesisMemoryDecision,
    InformationValueRecord,
    ResearchContradiction,
    ResearchMemoryEntry,
    ResearchMethodReliability,
    ResearchOutcomeAttribution,
    ResearchRegimeAssignment,
    ResearchRegimeDefinition,
    SignalIndependenceAnalysis,
)
from packages.research_intelligence.fixtures import seed_reference_research_intelligence
from packages.research_intelligence.service import divergence_as_of, memory_as_of

router = APIRouter(tags=["research-intelligence"])


def _workspace_id(session: Session) -> uuid.UUID:
    value = session.info.get("workspace_id")
    if not isinstance(value, uuid.UUID):
        raise HTTPException(status_code=403, detail="Workspace context is required")
    return value


def _memory(item: ResearchMemoryEntry, company_name: str | None = None) -> dict[str, object]:
    return {
        "id": str(item.id),
        "hypothesis_id": str(item.hypothesis_id),
        "experiment_id": str(item.experiment_id),
        "subject_entity_id": str(item.subject_entity_id),
        "company_name": company_name,
        "hypothesis_version": item.hypothesis_version,
        "feature_key": item.feature_key,
        "feature_version": item.feature_version,
        "outcome_key": item.outcome_key,
        "conclusion": item.conclusion,
        "status": item.status,
        "datasets": item.datasets,
        "feature_domains": item.feature_domains,
        "applicability": item.applicability,
        "regime_context": item.regime_context,
        "period_context": item.period_context,
        "result_summary": item.result_summary,
        "failure_reasons": item.failure_reasons,
        "success_conditions": item.success_conditions,
        "failure_conditions": item.failure_conditions,
        "confidence": str(item.confidence),
        "first_learned_at": item.first_learned_at,
        "last_confirmed_at": item.last_confirmed_at,
        "simulation_eligible_time": item.simulation_eligible_time,
        "schema_version": item.schema_version,
        "semantics": "historical_research_memory_not_investment_advice",
    }


@router.post("/research/intelligence/reference-fixture")
def create_reference_fixture(session: Session = Depends(get_db)) -> dict[str, object]:
    result = seed_reference_research_intelligence(session, _workspace_id(session))
    session.commit()
    return result


@router.get("/research/memory")
def list_memory(
    as_of: datetime | None = Query(default=None), session: Session = Depends(get_db)
) -> dict[str, object]:
    workspace_id = _workspace_id(session)
    if as_of is not None:
        items = memory_as_of(session, workspace_id, as_of)
    else:
        items = list(
            session.scalars(
                select(ResearchMemoryEntry)
                .where(ResearchMemoryEntry.workspace_id == workspace_id)
                .order_by(
                    ResearchMemoryEntry.simulation_eligible_time.desc(),
                    ResearchMemoryEntry.id,
                )
            )
        )
    names = {
        entity.id: entity.canonical_name
        for entity in session.scalars(
            select(EconomicEntity).where(
                EconomicEntity.id.in_([item.subject_entity_id for item in items])
            )
        )
    }
    return {"items": [_memory(item, names.get(item.subject_entity_id)) for item in items]}


@router.get("/research/memory/search")
def search_memory(
    query: str | None = Query(default=None),
    conclusion: str | None = Query(default=None),
    feature_key: str | None = Query(default=None),
    outcome_key: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    statement = select(ResearchMemoryEntry).where(
        ResearchMemoryEntry.workspace_id == _workspace_id(session)
    )
    if query:
        pattern = f"%{query}%"
        statement = statement.where(
            or_(
                ResearchMemoryEntry.feature_key.ilike(pattern),
                ResearchMemoryEntry.outcome_key.ilike(pattern),
                ResearchMemoryEntry.mechanism_checksum.ilike(pattern),
            )
        )
    if conclusion:
        statement = statement.where(ResearchMemoryEntry.conclusion == conclusion.upper())
    if feature_key:
        statement = statement.where(ResearchMemoryEntry.feature_key == feature_key)
    if outcome_key:
        statement = statement.where(ResearchMemoryEntry.outcome_key == outcome_key)
    items = list(session.scalars(statement.order_by(ResearchMemoryEntry.first_learned_at.desc())))
    return {"items": [_memory(item) for item in items], "deterministic": True}


@router.get("/research/memory/{memory_id}")
def memory_detail(memory_id: uuid.UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    item = session.scalar(
        select(ResearchMemoryEntry).where(
            ResearchMemoryEntry.id == memory_id,
            ResearchMemoryEntry.workspace_id == _workspace_id(session),
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Research memory was not found")
    all_decisions = list(
        session.scalars(
            select(HypothesisMemoryDecision).where(
                HypothesisMemoryDecision.workspace_id == item.workspace_id
            )
        )
    )
    decisions = [
        decision
        for decision in all_decisions
        if decision.hypothesis_id == item.hypothesis_id
        or str(item.id) in decision.matched_memory_ids
    ]
    return {
        **_memory(item),
        "graph_path": item.graph_path,
        "provenance": item.provenance,
        "memory_decisions": [
            {
                "classification": decision.classification,
                "decision": decision.decision,
                "reason": decision.reason,
                "override_authorized": decision.override_authorized,
                "policy_version": decision.policy_version,
            }
            for decision in decisions
        ],
    }


@router.get("/research/contradictions")
def contradictions(session: Session = Depends(get_db)) -> dict[str, object]:
    items = list(
        session.scalars(
            select(ResearchContradiction)
            .where(ResearchContradiction.workspace_id == _workspace_id(session))
            .order_by(ResearchContradiction.discovered_at.desc())
        )
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "memory_a_id": str(item.memory_a_id),
                "memory_b_id": str(item.memory_b_id),
                "conflicting_dimension": item.conflicting_dimension,
                "context": item.context,
                "confidence": str(item.confidence),
                "possible_explanations": item.possible_explanations,
                "discovered_at": item.discovered_at,
                "causally_explained": False,
            }
            for item in items
        ]
    }


@router.get("/research/regimes")
def regimes(session: Session = Depends(get_db)) -> dict[str, object]:
    workspace_id = _workspace_id(session)
    definitions = list(
        session.scalars(
            select(ResearchRegimeDefinition).where(
                ResearchRegimeDefinition.workspace_id == workspace_id
            )
        )
    )
    assignments = list(
        session.scalars(
            select(ResearchRegimeAssignment).where(
                ResearchRegimeAssignment.workspace_id == workspace_id
            )
        )
    )
    return {
        "definitions": [
            {
                "id": str(item.id),
                "key": item.key,
                "label": item.label,
                "method": item.method,
                "version": item.version,
            }
            for item in definitions
        ],
        "assignments": [
            {
                "definition_id": str(item.definition_id),
                "subject_entity_id": str(item.subject_entity_id)
                if item.subject_entity_id
                else None,
                "as_of_time": item.as_of_time,
                "active": item.active,
                "evidence": item.evidence,
            }
            for item in assignments
        ],
    }


def _independence(item: SignalIndependenceAnalysis) -> dict[str, object]:
    return {
        "id": str(item.id),
        "experiment_id": str(item.experiment_id),
        "factor_key": item.factor_key,
        "baseline_version": item.baseline_version,
        "methodology_version": item.methodology_version,
        "predictive_strength": str(item.predictive_strength),
        "independent_contribution": str(item.independent_contribution),
        "redundancy_score": str(item.redundancy_score),
        "independent_information_score": str(item.independent_information_score),
        "components": item.components,
        "formula": item.formula,
        "segments": item.segments,
        "as_of_time": item.as_of_time,
        "semantics": "predictive_is_not_independent_and_independent_is_not_causal",
    }


@router.get("/research/signal-independence")
def independence(session: Session = Depends(get_db)) -> dict[str, object]:
    items = list(
        session.scalars(
            select(SignalIndependenceAnalysis)
            .where(SignalIndependenceAnalysis.workspace_id == _workspace_id(session))
            .order_by(SignalIndependenceAnalysis.independent_information_score.desc())
        )
    )
    return {"items": [_independence(item) for item in items]}


@router.get("/research/signal-independence/{analysis_id}")
def independence_detail(
    analysis_id: uuid.UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    item = session.scalar(
        select(SignalIndependenceAnalysis).where(
            SignalIndependenceAnalysis.id == analysis_id,
            SignalIndependenceAnalysis.workspace_id == _workspace_id(session),
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Signal independence analysis was not found")
    return _independence(item)


@router.get("/research/factor-redundancy")
def redundancy(session: Session = Depends(get_db)) -> dict[str, object]:
    items = list(
        session.scalars(
            select(FactorRedundancyResult).where(
                FactorRedundancyResult.workspace_id == _workspace_id(session)
            )
        )
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "factor_a": item.factor_a,
                "factor_b": item.factor_b,
                "methodology": item.methodology,
                "parameters": item.parameters,
                "result": item.result,
                "as_of_time": item.as_of_time,
            }
            for item in items
        ]
    }


@router.get("/research/factor-clusters")
def clusters(session: Session = Depends(get_db)) -> dict[str, object]:
    items = list(
        session.scalars(
            select(FactorCluster).where(FactorCluster.workspace_id == _workspace_id(session))
        )
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "cluster_key": item.cluster_key,
                "information_family": item.information_family,
                "members": item.members,
                "methodology": item.methodology,
                "version": item.version,
            }
            for item in items
        ],
        "causal_structure_claimed": False,
    }


@router.get("/research/divergence-definitions")
def divergence_definitions(session: Session = Depends(get_db)) -> dict[str, object]:
    items = list(
        session.scalars(
            select(DivergenceDefinition).where(
                DivergenceDefinition.workspace_id == _workspace_id(session)
            )
        )
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "key": item.key,
                "name": item.name,
                "domains": item.domains,
                "required_features": item.required_features,
                "rules": item.rules,
                "temporal_truth_policy": item.temporal_truth_policy,
                "version": item.version,
            }
            for item in items
        ]
    }


def _divergence(item: DivergenceEvent, company_name: str | None = None) -> dict[str, object]:
    return {
        "id": str(item.id),
        "definition_id": str(item.definition_id),
        "subject_entity_id": str(item.subject_entity_id),
        "company_name": company_name,
        "as_of_time": item.as_of_time,
        "domain_values": item.domain_values,
        "magnitude_components": item.magnitude_components,
        "disagreement_magnitude": str(item.disagreement_magnitude),
        "persistence_periods": item.persistence_periods,
        "data_completeness": str(item.data_completeness),
        "evidence": item.evidence,
        "historical_analogues": item.historical_analogues,
        "confidence": str(item.confidence),
        "research_priority": str(item.research_priority),
        "status": item.status,
        "research_candidate_id": (
            str(item.research_candidate_id) if item.research_candidate_id else None
        ),
        "paper_eligible": False,
        "semantics": "divergent_not_mispriced_or_trade_instruction",
    }


@router.get("/research/divergence-events")
def divergence_events(
    as_of: datetime | None = Query(default=None), session: Session = Depends(get_db)
) -> dict[str, object]:
    workspace_id = _workspace_id(session)
    items = (
        divergence_as_of(session, workspace_id, as_of)
        if as_of is not None
        else list(
            session.scalars(
                select(DivergenceEvent).where(DivergenceEvent.workspace_id == workspace_id)
            )
        )
    )
    names = {
        item.id: item.canonical_name
        for item in session.scalars(
            select(EconomicEntity).where(
                EconomicEntity.id.in_([event.subject_entity_id for event in items])
            )
        )
    }
    return {"items": [_divergence(item, names.get(item.subject_entity_id)) for item in items]}


@router.get("/research/divergence-events/{event_id}")
def divergence_detail(event_id: uuid.UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    item = session.scalar(
        select(DivergenceEvent).where(
            DivergenceEvent.id == event_id,
            DivergenceEvent.workspace_id == _workspace_id(session),
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Divergence event was not found")
    entity = session.get(EconomicEntity, item.subject_entity_id)
    return _divergence(item, entity.canonical_name if entity else None)


@router.get("/research/information-value")
def information_value(session: Session = Depends(get_db)) -> dict[str, object]:
    items = list(
        session.scalars(
            select(InformationValueRecord).where(
                InformationValueRecord.workspace_id == _workspace_id(session)
            )
        )
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "resource_key": item.resource_key,
                "resource_type": item.resource_type,
                "metrics": item.metrics,
                "recommendation": item.recommendation,
                "sample_size": item.sample_size,
                "as_of_time": item.as_of_time,
            }
            for item in items
        ],
        "semantics": "research_resource_efficiency_not_investment_roi",
    }


@router.get("/research/method-reliability")
def method_reliability(session: Session = Depends(get_db)) -> dict[str, object]:
    items = list(
        session.scalars(
            select(ResearchMethodReliability).where(
                ResearchMethodReliability.workspace_id == _workspace_id(session)
            )
        )
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "method": item.method,
                "metrics": item.metrics,
                "sample_size": item.sample_size,
                "interpretation": item.interpretation,
                "as_of_time": item.as_of_time,
            }
            for item in items
        ]
    }


@router.get("/research/outcome-attribution")
def outcome_attribution(session: Session = Depends(get_db)) -> dict[str, object]:
    items = list(
        session.scalars(
            select(ResearchOutcomeAttribution).where(
                ResearchOutcomeAttribution.workspace_id == _workspace_id(session)
            )
        )
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "experiment_id": str(item.experiment_id),
                "reason_code": item.reason_code,
                "category": item.category,
                "passed": item.passed,
                "evidence": item.evidence,
                "simulation_eligible_time": item.simulation_eligible_time,
            }
            for item in items
        ]
    }
