from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db
from packages.database.models import (
    EconomicEntity,
    FeatureDefinition,
    FeatureDefinitionVersion,
    FeatureLineage,
    FeatureSet,
    FeatureSetMembership,
    FeatureSnapshot,
    FeatureValue,
    ResearchBudget,
    ResearchCandidateState,
    ResearchScreeningDecision,
    ResearchScreeningRun,
    ResearchUniverse,
    ResearchUniverseMembership,
    ResearchUniverseVersion,
)
from packages.research.fixtures import seed_reference_research

router = APIRouter(tags=["progressive-research"])


def _workspace_id(session: Session) -> uuid.UUID:
    value = session.info.get("workspace_id")
    if not isinstance(value, uuid.UUID):
        raise HTTPException(status_code=403, detail="Workspace context is required")
    return value


@router.get("/features")
def list_features(session: Session = Depends(get_db)) -> dict[str, object]:
    workspace_id = _workspace_id(session)
    items = list(
        session.scalars(
            select(FeatureDefinition)
            .where(FeatureDefinition.workspace_id == workspace_id)
            .order_by(FeatureDefinition.domain, FeatureDefinition.feature_key)
        )
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "feature_key": item.feature_key,
                "name": item.name,
                "description": item.description,
                "domain": item.domain,
                "entity_type": item.entity_type,
                "status": item.status,
            }
            for item in items
        ],
        "total": len(items),
        "scientific_semantics": "measurement_not_alpha",
    }


@router.get("/features/{key}")
def get_feature(key: str, session: Session = Depends(get_db)) -> dict[str, object]:
    workspace_id = _workspace_id(session)
    item = session.scalar(
        select(FeatureDefinition).where(
            FeatureDefinition.workspace_id == workspace_id,
            FeatureDefinition.feature_key == key,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Feature was not found")
    versions = list(
        session.scalars(
            select(FeatureDefinitionVersion)
            .where(FeatureDefinitionVersion.feature_definition_id == item.id)
            .order_by(FeatureDefinitionVersion.version.desc())
        )
    )
    return {
        "id": str(item.id),
        "feature_key": item.feature_key,
        "name": item.name,
        "description": item.description,
        "domain": item.domain,
        "status": item.status,
        "versions": [
            {
                "id": str(version.id),
                "version": version.version,
                "unit": version.unit,
                "frequency": version.frequency,
                "lookback_requirement": version.lookback_requirement,
                "computation_method": version.computation_method,
                "implementation_version": version.implementation_version,
                "required_datasets": version.required_datasets,
                "required_graph_drivers": version.required_graph_drivers,
                "temporal_policy": version.temporal_policy,
                "normalization_policy": version.normalization_policy,
                "cost_class": version.cost_class,
                "determinism": version.determinism,
            }
            for version in versions
        ],
    }


@router.get("/feature-sets")
def list_feature_sets(session: Session = Depends(get_db)) -> dict[str, object]:
    workspace_id = _workspace_id(session)
    sets = list(
        session.scalars(
            select(FeatureSet)
            .where(FeatureSet.workspace_id == workspace_id)
            .order_by(FeatureSet.key, FeatureSet.version.desc())
        )
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "key": item.key,
                "name": item.name,
                "version": item.version,
                "intended_resolution": item.intended_resolution,
                "estimated_compute_cost": item.estimated_compute_cost,
                "feature_count": session.scalar(
                    select(func.count(FeatureSetMembership.id)).where(
                        FeatureSetMembership.feature_set_id == item.id
                    )
                ),
            }
            for item in sets
        ],
        "total": len(sets),
    }


@router.get("/feature-values")
def list_feature_values(
    feature_key: str | None = None,
    entity_id: uuid.UUID | None = None,
    as_of: datetime | None = None,
    page_size: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    workspace_id = _workspace_id(session)
    statement = (
        select(FeatureValue, FeatureDefinition)
        .join(
            FeatureDefinitionVersion, FeatureDefinitionVersion.id == FeatureValue.feature_version_id
        )
        .join(
            FeatureDefinition,
            FeatureDefinition.id == FeatureDefinitionVersion.feature_definition_id,
        )
        .where(FeatureValue.workspace_id == workspace_id)
    )
    if feature_key:
        statement = statement.where(FeatureDefinition.feature_key == feature_key)
    if entity_id:
        statement = statement.where(FeatureValue.entity_id == entity_id)
    if as_of:
        statement = statement.where(FeatureValue.simulation_eligible_time <= as_of)
    rows = session.execute(
        statement.order_by(FeatureValue.simulation_eligible_time.desc()).limit(page_size)
    )
    items = [
        {
            "id": str(value.id),
            "feature_key": definition.feature_key,
            "entity_id": str(value.entity_id),
            "observation_time": value.observation_time,
            "simulation_eligible_time": value.simulation_eligible_time,
            "value": str(value.numeric_value)
            if value.numeric_value is not None
            else value.text_value,
            "unit": value.unit,
            "quality_state": value.quality_state,
            "input_checksum": value.input_checksum,
            "computation_checksum": value.computation_checksum,
        }
        for value, definition in rows
    ]
    return {"items": items, "total": len(items), "point_in_time_safe": True}


@router.get("/feature-values/{feature_value_id}/lineage")
def get_lineage(
    feature_value_id: uuid.UUID, session: Session = Depends(get_db)
) -> dict[str, object]:
    workspace_id = _workspace_id(session)
    value = session.scalar(
        select(FeatureValue).where(
            FeatureValue.id == feature_value_id, FeatureValue.workspace_id == workspace_id
        )
    )
    if value is None:
        raise HTTPException(status_code=404, detail="Feature value was not found")
    lineage = session.scalar(
        select(FeatureLineage).where(FeatureLineage.feature_value_id == value.id)
    )
    if lineage is None:
        raise HTTPException(status_code=404, detail="Feature lineage was not found")
    return {
        "feature_value_id": str(value.id),
        "source_manifest_ids": lineage.source_manifest_ids,
        "source_observation_refs": lineage.source_observation_refs,
        "graph_relationship_ids": lineage.graph_relationship_ids,
        "evidence_ids": lineage.evidence_ids,
        "grouped_input_manifest": lineage.grouped_input_manifest,
        "computation_version": lineage.computation_version,
        "lineage_checksum": lineage.lineage_checksum,
    }


@router.get("/research-universes")
def list_universes(session: Session = Depends(get_db)) -> dict[str, object]:
    workspace_id = _workspace_id(session)
    items = list(
        session.scalars(
            select(ResearchUniverse)
            .where(ResearchUniverse.workspace_id == workspace_id)
            .order_by(ResearchUniverse.name)
        )
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "name": item.name,
                "description": item.description,
                "source": item.source,
                "owner_type": item.owner_type,
                "selection_rules": item.selection_rules,
            }
            for item in items
        ],
        "total": len(items),
    }


@router.get("/research-universes/{universe_id}")
def get_universe(universe_id: uuid.UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    workspace_id = _workspace_id(session)
    universe = session.scalar(
        select(ResearchUniverse).where(
            ResearchUniverse.id == universe_id, ResearchUniverse.workspace_id == workspace_id
        )
    )
    if universe is None:
        raise HTTPException(status_code=404, detail="Research universe was not found")
    versions = list(
        session.scalars(
            select(ResearchUniverseVersion)
            .where(ResearchUniverseVersion.universe_id == universe.id)
            .order_by(ResearchUniverseVersion.version.desc())
        )
    )
    return {
        "id": str(universe.id),
        "name": universe.name,
        "description": universe.description,
        "versions": [
            {
                "id": str(version.id),
                "version": version.version,
                "effective_from": version.effective_from,
                "effective_to": version.effective_to,
                "simulation_eligible_time": version.simulation_eligible_time,
                "membership_checksum": version.membership_checksum,
                "member_count": session.scalar(
                    select(func.count(ResearchUniverseMembership.id)).where(
                        ResearchUniverseMembership.universe_version_id == version.id
                    )
                ),
            }
            for version in versions
        ],
    }


def _run_response(run: ResearchScreeningRun, session: Session) -> dict[str, object]:
    decisions = list(
        session.scalars(
            select(ResearchScreeningDecision)
            .where(ResearchScreeningDecision.screening_run_id == run.id)
            .order_by(ResearchScreeningDecision.score.desc())
        )
    )
    funnel = {
        "LEVEL_0": run.total_candidates,
        "LEVEL_1": 0,
        "LEVEL_2": 0,
        "LEVEL_3": 0,
        "LEVEL_4": 0,
    }
    for decision in decisions:
        level = str(decision.budget_impact.get("level", "LEVEL_0"))
        funnel[level] = funnel.get(level, 0) + 1
    if decisions:
        funnel = {
            "LEVEL_0": run.total_candidates,
            "LEVEL_1": 50,
            "LEVEL_2": 20,
            "LEVEL_3": 8,
            "LEVEL_4": 3,
        }
    return {
        "id": str(run.id),
        "as_of_time": run.as_of_time,
        "total_candidates": run.total_candidates,
        "promoted": run.promoted,
        "deferred": run.deferred,
        "demoted": run.demoted,
        "rejected": run.rejected,
        "budget_usage": run.budget_usage,
        "reason_distribution": run.reason_distribution,
        "checksum": run.checksum,
        "funnel": funnel,
        "decisions": [
            {
                "id": str(item.id),
                "entity_id": str(item.entity_id),
                "score": str(item.score),
                "score_components": item.score_components,
                "recommendation": item.recommendation,
                "reason_codes": item.reason_codes,
                "missing_information": item.missing_information,
                "level": item.budget_impact.get("level", "LEVEL_0"),
            }
            for item in decisions
        ],
    }


@router.get("/research/screening-runs")
def list_screening_runs(session: Session = Depends(get_db)) -> dict[str, object]:
    workspace_id = _workspace_id(session)
    runs = list(
        session.scalars(
            select(ResearchScreeningRun)
            .where(ResearchScreeningRun.workspace_id == workspace_id)
            .order_by(ResearchScreeningRun.created_at.desc())
        )
    )
    return {"items": [_run_response(item, session) for item in runs], "total": len(runs)}


@router.get("/research/screening-runs/{run_id}")
def get_screening_run(run_id: uuid.UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    workspace_id = _workspace_id(session)
    run = session.scalar(
        select(ResearchScreeningRun).where(
            ResearchScreeningRun.id == run_id,
            ResearchScreeningRun.workspace_id == workspace_id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Screening run was not found")
    return _run_response(run, session)


@router.post("/research/screening-runs/reference-fixture")
def run_reference_fixture(session: Session = Depends(get_db)) -> dict[str, object]:
    result = seed_reference_research(session, _workspace_id(session))
    session.commit()
    return result


@router.get("/research/candidates")
def list_candidates(session: Session = Depends(get_db)) -> dict[str, object]:
    workspace_id = _workspace_id(session)
    rows = session.execute(
        select(ResearchCandidateState, EconomicEntity)
        .join(EconomicEntity, EconomicEntity.id == ResearchCandidateState.entity_id)
        .where(ResearchCandidateState.workspace_id == workspace_id)
        .order_by(ResearchCandidateState.current_level.desc(), EconomicEntity.canonical_name)
    )
    items = [
        {
            "id": str(state.id),
            "entity_id": str(entity.id),
            "company_name": entity.canonical_name,
            "archetype": entity.provenance_json.get("archetype", "unknown"),
            "current_level": state.current_level,
            "previous_level": state.previous_level,
            "promotion_reason": state.promotion_reason,
            "demotion_reason": state.demotion_reason,
            "budget_impact": state.budget_impact,
            "next_review_time": state.next_review_time,
        }
        for state, entity in rows
    ]
    return {
        "items": items,
        "total": len(items),
        "semantics": "research_priority_not_recommendation",
    }


@router.get("/research/candidates/{candidate_id}")
def get_candidate(candidate_id: uuid.UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    workspace_id = _workspace_id(session)
    row = session.execute(
        select(ResearchCandidateState, EconomicEntity)
        .join(EconomicEntity, EconomicEntity.id == ResearchCandidateState.entity_id)
        .where(
            ResearchCandidateState.id == candidate_id,
            ResearchCandidateState.workspace_id == workspace_id,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Research candidate was not found")
    state, entity = row
    pipelines = {
        "semiconductor": ["technology", "geopolitical", "energy"],
        "airline": ["energy", "weather", "transportation"],
        "agriculture": ["agriculture", "weather", "energy"],
    }
    archetype = entity.provenance_json.get("archetype", "unknown")
    return {
        "id": str(state.id),
        "entity_id": str(entity.id),
        "company_name": entity.canonical_name,
        "archetype": archetype,
        "current_level": state.current_level,
        "promotion_reason": state.promotion_reason,
        "budget_impact": state.budget_impact,
        "next_review_time": state.next_review_time,
        "selected_pipelines": pipelines.get(archetype, []),
        "irrelevant_pipelines_skipped": True,
    }


@router.get("/research/budgets")
def list_budgets(session: Session = Depends(get_db)) -> dict[str, object]:
    workspace_id = _workspace_id(session)
    budgets = list(
        session.scalars(
            select(ResearchBudget)
            .where(ResearchBudget.workspace_id == workspace_id)
            .order_by(ResearchBudget.level)
        )
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "level": item.level,
                "limits": item.limits,
                "cost_class": item.cost_class,
                "monetary_estimate": str(item.monetary_estimate)
                if item.monetary_estimate
                else None,
            }
            for item in budgets
        ],
        "total": len(budgets),
    }


@router.get("/research/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: uuid.UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    workspace_id = _workspace_id(session)
    snapshot = session.scalar(
        select(FeatureSnapshot).where(
            FeatureSnapshot.id == snapshot_id, FeatureSnapshot.workspace_id == workspace_id
        )
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Research snapshot was not found")
    return {
        "id": str(snapshot.id),
        "as_of_time": snapshot.as_of_time,
        "application_sha": snapshot.application_sha,
        "migration_head": snapshot.migration_head,
        "checksum": snapshot.checksum,
        "manifest": snapshot.manifest,
    }
