from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db, get_workspace_context, require_permission
from packages.database.models import (
    CompanyDriverEntry,
    CompanyDriverProfile,
    DataRelevanceDecision,
    EconomicEntity,
    EconomicRelationship,
    EntityAlias,
    EntityIdentifier,
    EntityResolutionCandidate,
    EvidenceRecord,
    RelationshipEvidence,
)
from packages.economic_graph.service import decide_resolution
from packages.economic_graph.traversal import (
    GraphLimitError,
    bounded_graph_as_of,
    explain_relationship_path,
)
from packages.provenance import record_audit_event
from packages.security import WorkspaceContext

router = APIRouter(tags=["economic-graph"])


class ResolutionDecisionPayload(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


def _entity(item: EconomicEntity) -> dict[str, Any]:
    return {
        "id": item.id,
        "workspace_id": item.workspace_id,
        "entity_type": item.entity_type,
        "canonical_name": item.canonical_name,
        "status": item.status,
        "valid_from": item.valid_from,
        "valid_to": item.valid_to,
        "first_seen": item.first_seen,
        "last_verified": item.last_verified,
        "simulation_eligible_time": item.simulation_eligible_time,
        "confidence": str(item.confidence),
        "provenance": item.provenance_json,
    }


def _relationship(item: EconomicRelationship) -> dict[str, Any]:
    return {
        "id": item.id,
        "subject_entity_id": item.subject_entity_id,
        "predicate": item.predicate,
        "object_entity_id": item.object_entity_id,
        "confidence": str(item.confidence),
        "strength": str(item.strength) if item.strength is not None else None,
        "valid_from": item.valid_from,
        "valid_to": item.valid_to,
        "discovered_at": item.discovered_at,
        "last_verified_at": item.last_verified_at,
        "simulation_eligible_time": item.simulation_eligible_time,
        "method": item.method,
        "method_version": item.method_version,
        "status": item.status,
    }


@router.get("/entities")
def list_entities(
    entity_type: str | None = None,
    status: str | None = None,
    query: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    statement = select(EconomicEntity)
    count_statement = select(func.count(EconomicEntity.id))
    conditions: list[Any] = []
    if entity_type:
        conditions.append(EconomicEntity.entity_type == entity_type)
    if status:
        conditions.append(EconomicEntity.status == status)
    if query:
        conditions.append(EconomicEntity.normalized_name.contains(query.casefold()))
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)
    items = session.scalars(
        statement.order_by(EconomicEntity.entity_type, EconomicEntity.canonical_name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [_entity(item) for item in items],
        "page": page,
        "page_size": page_size,
        "total": session.scalar(count_statement) or 0,
    }


@router.get("/entities/{entity_id}")
def get_entity(entity_id: uuid.UUID, session: Session = Depends(get_db)) -> dict[str, Any]:
    item = session.get(EconomicEntity, entity_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Economic entity not found")
    result = _entity(item)
    result["identifiers"] = [
        {
            "id": value.id,
            "namespace": value.namespace,
            "value": value.value,
            "method": value.mapping_method,
            "confidence": str(value.confidence),
            "simulation_eligible_time": value.simulation_eligible_time,
        }
        for value in session.scalars(
            select(EntityIdentifier)
            .where(EntityIdentifier.entity_id == item.id)
            .order_by(EntityIdentifier.namespace, EntityIdentifier.normalized_value)
        )
    ]
    result["aliases"] = [
        {"id": value.id, "alias": value.alias, "source": value.source}
        for value in session.scalars(
            select(EntityAlias)
            .where(EntityAlias.entity_id == item.id)
            .order_by(EntityAlias.normalized_alias)
        )
    ]
    return result


@router.get("/entities/{entity_id}/relationships")
def get_entity_relationships(
    entity_id: uuid.UUID,
    as_of: datetime | None = None,
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    cutoff = as_of or datetime.now(UTC)
    if cutoff.tzinfo is None:
        raise HTTPException(status_code=422, detail="as_of must include a timezone")
    items = session.scalars(
        select(EconomicRelationship).where(
            or_(
                EconomicRelationship.subject_entity_id == entity_id,
                EconomicRelationship.object_entity_id == entity_id,
            ),
            EconomicRelationship.simulation_eligible_time <= cutoff,
            EconomicRelationship.valid_from <= cutoff,
            or_(EconomicRelationship.valid_to.is_(None), EconomicRelationship.valid_to > cutoff),
        ).order_by(EconomicRelationship.predicate, EconomicRelationship.id)
    ).all()
    return {"items": [_relationship(item) for item in items], "total": len(items), "as_of": cutoff}


@router.get("/entities/{entity_id}/evidence")
def get_entity_evidence(
    entity_id: uuid.UUID, session: Session = Depends(get_db)
) -> dict[str, Any]:
    rows = session.execute(
        select(RelationshipEvidence, EvidenceRecord, EconomicRelationship)
        .join(EvidenceRecord, EvidenceRecord.id == RelationshipEvidence.evidence_id)
        .join(EconomicRelationship, EconomicRelationship.id == RelationshipEvidence.relationship_id)
        .where(
            or_(
                EconomicRelationship.subject_entity_id == entity_id,
                EconomicRelationship.object_entity_id == entity_id,
            )
        )
        .order_by(EvidenceRecord.publication_time, EvidenceRecord.id)
    ).all()
    return {
        "items": [
            {
                "id": evidence.id,
                "relationship_id": relationship.id,
                "direction": link.direction,
                "source_record_identifier": evidence.source_record_identifier,
                "evidence_type": evidence.evidence_type,
                "publication_time": evidence.publication_time,
                "simulation_eligible_time": evidence.simulation_eligible_time,
                "confidence": str(evidence.confidence),
                "content_reference": evidence.content_reference,
                "supporting_text": evidence.supporting_text,
            }
            for link, evidence, relationship in rows
        ],
        "total": len(rows),
    }


def _latest_profile(
    session: Session, company_id: uuid.UUID
) -> CompanyDriverProfile:
    profile = session.scalar(
        select(CompanyDriverProfile)
        .where(CompanyDriverProfile.company_entity_id == company_id)
        .order_by(CompanyDriverProfile.version.desc())
        .limit(1)
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Company driver profile not found")
    return profile


@router.get("/companies/{company_id}/driver-profile")
def get_driver_profile(
    company_id: uuid.UUID, session: Session = Depends(get_db)
) -> dict[str, Any]:
    profile = _latest_profile(session, company_id)
    entries = session.scalars(
        select(CompanyDriverEntry)
        .where(CompanyDriverEntry.profile_id == profile.id)
        .order_by(CompanyDriverEntry.effective_relevance.desc(), CompanyDriverEntry.driver_category)
    ).all()
    return {
        "id": profile.id,
        "company_entity_id": profile.company_entity_id,
        "prior_version": profile.prior_version,
        "version": profile.version,
        "generated_at": profile.generated_at,
        "simulation_eligible_time": profile.simulation_eligible_time,
        "trigger_reason": profile.trigger_reason,
        "scientific_label": "potential driver; not a historically validated factor",
        "entries": [
            {
                "id": item.id,
                "driver_category": item.driver_category,
                "linked_entity_ids": item.linked_entity_ids,
                "supporting_relationship_ids": item.supporting_relationship_ids,
                "prior_relevance": str(item.prior_relevance),
                "evidence_relevance": str(item.evidence_relevance),
                "historical_evidence_relevance": (
                    str(item.historical_evidence_relevance)
                    if item.historical_evidence_relevance is not None
                    else None
                ),
                "user_override": (
                    str(item.user_override) if item.user_override is not None else None
                ),
                "effective_relevance": str(item.effective_relevance),
                "confidence": str(item.confidence),
                "explanation": item.explanation,
            }
            for item in entries
        ],
    }


@router.get("/companies/{company_id}/driver-paths")
def get_driver_paths(
    company_id: uuid.UUID,
    as_of: datetime | None = None,
    max_depth: int = Query(default=3, ge=1, le=5),
    max_nodes: int = Query(default=100, ge=1, le=500),
    timeout_ms: int = Query(default=500, ge=10, le=5000),
    context: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    cutoff = as_of or datetime.now(UTC)
    try:
        graph = bounded_graph_as_of(
            session,
            workspace_id=context.workspace_id,
            start_entity_id=company_id,
            as_of=cutoff,
            max_depth=max_depth,
            max_nodes=max_nodes,
            timeout_ms=timeout_ms,
        )
    except (GraphLimitError, LookupError, ValueError) as exc:
        status = 404 if isinstance(exc, LookupError) else 422
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    graph["path_explanations"] = [
        {
            **path,
            "explanation": explain_relationship_path(
                session,
                [uuid.UUID(value) for value in path["relationship_ids"]],
                as_of=cutoff,
            ),
        }
        for path in graph["paths"]
    ]
    return graph


@router.get("/companies/{company_id}/data-relevance")
def get_data_relevance(
    company_id: uuid.UUID, session: Session = Depends(get_db)
) -> dict[str, Any]:
    profile = _latest_profile(session, company_id)
    items = session.scalars(
        select(DataRelevanceDecision)
        .where(DataRelevanceDecision.profile_id == profile.id)
        .order_by(
            DataRelevanceDecision.decision,
            DataRelevanceDecision.relevance_score.desc(),
            DataRelevanceDecision.dataset_id,
        )
    ).all()
    return {
        "company_entity_id": company_id,
        "profile_id": profile.id,
        "router_version": items[0].router_version if items else None,
        "items": [
            {
                "id": item.id,
                "dataset_id": item.dataset_id,
                "decision": item.decision,
                "relevance_score": str(item.relevance_score),
                "reason_codes": item.reason_codes,
                "supporting_graph_paths": item.supporting_graph_paths,
                "confidence": str(item.confidence),
                "created_at": item.created_at,
            }
            for item in items
        ],
        "total": len(items),
    }


@router.get("/entity-resolution/candidates")
def get_resolution_candidates(
    status: str | None = None,
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    statement = select(EntityResolutionCandidate)
    if status:
        statement = statement.where(EntityResolutionCandidate.status == status)
    items = session.scalars(
        statement.order_by(EntityResolutionCandidate.resolved_at.desc()).limit(200)
    ).all()
    return {
        "items": [
            {
                "id": item.id,
                "namespace": item.namespace,
                "value": item.value,
                "normalized_value": item.normalized_value,
                "candidate_entity_id": item.candidate_entity_id,
                "method": item.method,
                "confidence": str(item.confidence),
                "source": item.source,
                "evidence": item.evidence_json,
                "resolver_version": item.resolver_version,
                "status": item.status,
                "resolved_at": item.resolved_at,
            }
            for item in items
        ],
        "total": len(items),
    }


def _resolution_decision(
    candidate_id: uuid.UUID,
    payload: ResolutionDecisionPayload,
    decision: str,
    context: WorkspaceContext,
    session: Session,
) -> dict[str, Any]:
    candidate = session.get(EntityResolutionCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Resolution candidate not found")
    try:
        item = decide_resolution(
            session,
            candidate,
            decision=decision,
            reason=payload.reason,
            user_id=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record_audit_event(
        session,
        action=f"entity_resolution.{decision}",
        entity_type="entity_resolution_candidate",
        entity_id=candidate.id,
        details={"reason": payload.reason},
    )
    session.commit()
    return {"id": item.id, "candidate_id": candidate.id, "decision": item.decision}


@router.post(
    "/entity-resolution/{candidate_id}/confirm",
    dependencies=[Depends(require_permission("graph.manage"))],
)
def confirm_resolution(
    candidate_id: uuid.UUID,
    payload: ResolutionDecisionPayload,
    context: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    return _resolution_decision(candidate_id, payload, "confirmed", context, session)


@router.post(
    "/entity-resolution/{candidate_id}/reject",
    dependencies=[Depends(require_permission("graph.manage"))],
)
def reject_resolution(
    candidate_id: uuid.UUID,
    payload: ResolutionDecisionPayload,
    context: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    return _resolution_decision(candidate_id, payload, "rejected", context, session)
