from __future__ import annotations

import time
import uuid
from collections import deque
from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session

from packages.database.models import (
    EconomicEntity,
    EconomicRelationship,
    EvidenceRecord,
    RelationshipEvidence,
)


class GraphLimitError(RuntimeError):
    pass


def _entity_visible(as_of: datetime) -> Any:
    return and_(
        EconomicEntity.simulation_eligible_time <= as_of,
        EconomicEntity.valid_from <= as_of,
        or_(EconomicEntity.valid_to.is_(None), EconomicEntity.valid_to > as_of),
        EconomicEntity.status.in_(("verified", "disputed")),
    )


def _relationship_visible(as_of: datetime) -> Any:
    return and_(
        EconomicRelationship.simulation_eligible_time <= as_of,
        EconomicRelationship.valid_from <= as_of,
        or_(
            EconomicRelationship.valid_to.is_(None),
            EconomicRelationship.valid_to > as_of,
        ),
        EconomicRelationship.status.in_(("verified", "disputed")),
    )


def bounded_graph_as_of(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    start_entity_id: uuid.UUID,
    as_of: datetime,
    max_depth: int = 3,
    max_nodes: int = 100,
    timeout_ms: int = 500,
    predicates: set[str] | None = None,
) -> dict[str, Any]:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    if not 1 <= max_depth <= 5:
        raise ValueError("max_depth must be between 1 and 5")
    if not 1 <= max_nodes <= 500:
        raise ValueError("max_nodes must be between 1 and 500")
    if not 10 <= timeout_ms <= 5_000:
        raise ValueError("timeout_ms must be between 10 and 5000")
    start = session.scalar(
        select(EconomicEntity).where(
            EconomicEntity.id == start_entity_id,
            EconomicEntity.workspace_id == workspace_id,
            _entity_visible(as_of),
        )
    )
    if start is None:
        raise LookupError("start entity is not visible at the requested time")
    started = time.monotonic()
    queue: deque[tuple[uuid.UUID, int, tuple[uuid.UUID, ...], tuple[uuid.UUID, ...]]] = deque(
        [(start.id, 0, (start.id,), ())]
    )
    entities: dict[uuid.UUID, EconomicEntity] = {start.id: start}
    relationships: dict[uuid.UUID, EconomicRelationship] = {}
    paths: list[dict[str, Any]] = []
    while queue:
        if (time.monotonic() - started) * 1000 > timeout_ms:
            raise GraphLimitError("graph traversal exceeded timeout")
        current_id, depth, entity_path, relationship_path = queue.popleft()
        if depth >= max_depth:
            continue
        edge_query = select(EconomicRelationship).where(
            EconomicRelationship.workspace_id == workspace_id,
            or_(
                EconomicRelationship.subject_entity_id == current_id,
                EconomicRelationship.object_entity_id == current_id,
            ),
            _relationship_visible(as_of),
        )
        if predicates:
            edge_query = edge_query.where(EconomicRelationship.predicate.in_(sorted(predicates)))
        edges = session.scalars(
            edge_query.order_by(
                EconomicRelationship.predicate,
                EconomicRelationship.subject_entity_id,
                EconomicRelationship.object_entity_id,
                EconomicRelationship.id,
            )
        ).all()
        for edge in edges:
            next_id = (
                edge.object_entity_id
                if edge.subject_entity_id == current_id
                else edge.subject_entity_id
            )
            if next_id in entity_path:
                continue
            next_entity = session.scalar(
                select(EconomicEntity).where(
                    EconomicEntity.id == next_id,
                    EconomicEntity.workspace_id == workspace_id,
                    _entity_visible(as_of),
                )
            )
            if next_entity is None:
                continue
            if next_id not in entities and len(entities) >= max_nodes:
                raise GraphLimitError("graph traversal exceeded node limit")
            entities[next_id] = next_entity
            relationships[edge.id] = edge
            next_entity_path = entity_path + (next_id,)
            next_relationship_path = relationship_path + (edge.id,)
            paths.append(
                {
                    "entity_ids": [str(value) for value in next_entity_path],
                    "relationship_ids": [str(value) for value in next_relationship_path],
                    "depth": depth + 1,
                }
            )
            queue.append((next_id, depth + 1, next_entity_path, next_relationship_path))
    return {
        "as_of": as_of,
        "max_depth": max_depth,
        "max_nodes": max_nodes,
        "nodes": [_serialize_entity(item) for item in sorted(entities.values(), key=_entity_key)],
        "relationships": [
            _serialize_relationship(item)
            for item in sorted(relationships.values(), key=_relationship_key)
        ],
        "paths": sorted(paths, key=lambda item: (item["depth"], item["entity_ids"])),
        "truncated": False,
    }


def postgres_recursive_neighborhood(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    start_entity_id: uuid.UUID,
    as_of: datetime,
    max_depth: int,
    max_nodes: int,
) -> list[dict[str, Any]]:
    """Run the production recursive CTE; callers use bounded_graph_as_of on SQLite."""

    if session.bind is None or session.bind.dialect.name != "postgresql":
        raise RuntimeError("recursive CTE plan is PostgreSQL-only")
    statement = text("""
        WITH RECURSIVE graph_walk(entity_id, depth, entity_path, relationship_path) AS (
          SELECT CAST(:start_id AS uuid), 0,
                 ARRAY[CAST(:start_id AS uuid)], ARRAY[]::uuid[]
          UNION ALL
          SELECT
            CASE WHEN relationship.subject_entity_id = graph_walk.entity_id
                 THEN relationship.object_entity_id ELSE relationship.subject_entity_id END,
            graph_walk.depth + 1,
            graph_walk.entity_path ||
              CASE WHEN relationship.subject_entity_id = graph_walk.entity_id
                   THEN relationship.object_entity_id ELSE relationship.subject_entity_id END,
            graph_walk.relationship_path || relationship.id
          FROM graph_walk
          JOIN economic_relationships AS relationship
            ON relationship.workspace_id = CAST(:workspace_id AS uuid)
           AND (relationship.subject_entity_id = graph_walk.entity_id
                OR relationship.object_entity_id = graph_walk.entity_id)
          WHERE graph_walk.depth < :max_depth
            AND relationship.status IN ('verified', 'disputed')
            AND relationship.simulation_eligible_time <= :as_of
            AND relationship.valid_from <= :as_of
            AND (relationship.valid_to IS NULL OR relationship.valid_to > :as_of)
            AND NOT (
              CASE WHEN relationship.subject_entity_id = graph_walk.entity_id
                   THEN relationship.object_entity_id ELSE relationship.subject_entity_id END
              = ANY(graph_walk.entity_path)
            )
        )
        SELECT entity_id, depth, entity_path, relationship_path
        FROM graph_walk
        ORDER BY depth, entity_path
        LIMIT :max_nodes
    """)
    rows = session.execute(
        statement,
        {
            "start_id": str(start_entity_id),
            "workspace_id": str(workspace_id),
            "max_depth": max_depth,
            "as_of": as_of,
            "max_nodes": max_nodes,
        },
    ).mappings()
    return [dict(row) for row in rows]


def explain_relationship_path(
    session: Session,
    relationship_ids: list[uuid.UUID],
    *,
    as_of: datetime,
) -> list[dict[str, Any]]:
    explained: list[dict[str, Any]] = []
    for relationship_id in relationship_ids:
        relationship = session.get(EconomicRelationship, relationship_id)
        if relationship is None or relationship.simulation_eligible_time > as_of:
            continue
        evidence_rows = session.execute(
            select(RelationshipEvidence, EvidenceRecord)
            .join(EvidenceRecord, EvidenceRecord.id == RelationshipEvidence.evidence_id)
            .where(
                RelationshipEvidence.relationship_id == relationship.id,
                EvidenceRecord.simulation_eligible_time <= as_of,
            )
            .order_by(RelationshipEvidence.direction, EvidenceRecord.source_record_identifier)
        ).all()
        explained.append(
            {
                "relationship": _serialize_relationship(relationship),
                "evidence": [
                    {
                        "id": str(record.id),
                        "direction": link.direction,
                        "source_record_identifier": record.source_record_identifier,
                        "evidence_type": record.evidence_type,
                        "publication_time": record.publication_time,
                        "simulation_eligible_time": record.simulation_eligible_time,
                        "confidence": str(record.confidence),
                        "content_reference": record.content_reference,
                    }
                    for link, record in evidence_rows
                ],
            }
        )
    return explained


def _entity_key(item: EconomicEntity) -> tuple[str, str, str]:
    return (item.entity_type, item.canonical_name.casefold(), str(item.id))


def _relationship_key(item: EconomicRelationship) -> tuple[str, str, str, str]:
    return (
        item.predicate,
        str(item.subject_entity_id),
        str(item.object_entity_id),
        str(item.id),
    )


def _serialize_entity(item: EconomicEntity) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "entity_type": item.entity_type,
        "canonical_name": item.canonical_name,
        "status": item.status,
        "valid_from": item.valid_from,
        "valid_to": item.valid_to,
        "simulation_eligible_time": item.simulation_eligible_time,
        "confidence": str(item.confidence),
    }


def _serialize_relationship(item: EconomicRelationship) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "subject_entity_id": str(item.subject_entity_id),
        "predicate": item.predicate,
        "object_entity_id": str(item.object_entity_id),
        "status": item.status,
        "valid_from": item.valid_from,
        "valid_to": item.valid_to,
        "simulation_eligible_time": item.simulation_eligible_time,
        "confidence": str(item.confidence),
    }
