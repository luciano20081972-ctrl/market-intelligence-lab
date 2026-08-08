from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, object_session

from packages.database.models import (
    EconomicEntity,
    EconomicRelationship,
    EntityAlias,
    EntityIdentifier,
    EntityResolutionCandidate,
    EntityResolutionDecision,
    EvidenceRecord,
    GraphQualityIssue,
    GraphRecomputeJob,
    RelationshipConfidenceComponent,
    RelationshipEvidence,
)
from packages.economic_graph.confidence import (
    CONFIDENCE_FORMULA_VERSION,
    aggregate_confidence,
)
from packages.economic_graph.types import ENTITY_TYPES, RELATIONSHIP_TYPES
from packages.world_data.temporal import TemporalTruth

VALID_ENTITY_STATUSES = {"candidate", "verified", "disputed", "expired", "rejected"}
VALID_RELATIONSHIP_STATUSES = VALID_ENTITY_STATUSES
IDENTIFIER_NAMESPACES = {
    "asset_id", "ticker", "exchange", "cik", "lei", "figi", "iso_country",
    "region", "fips", "provider_series", "facility_source_id",
}


def normalize_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
    if not normalized:
        raise ValueError("canonical name must contain letters or digits")
    return normalized


def normalize_identifier(namespace: str, value: str) -> str:
    if namespace not in IDENTIFIER_NAMESPACES:
        raise ValueError(f"unsupported identifier namespace: {namespace}")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("identifier value is required")
    if namespace == "cik":
        digits = cleaned.removeprefix("CIK").replace("-", "")
        if not digits.isdigit() or len(digits) > 10:
            raise ValueError("CIK must contain at most ten digits")
        return digits.zfill(10)
    if namespace in {"ticker", "exchange", "lei", "figi", "iso_country", "fips"}:
        return re.sub(r"\s+", "", cleaned).upper()
    if namespace == "provider_series":
        provider, separator, series_id = cleaned.partition(":")
        if not separator or not provider or not series_id:
            raise ValueError("provider_series identifiers use provider:series-id")
        return f"{provider.casefold()}:{series_id.strip()}"
    return cleaned.casefold()


def create_entity(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    entity_type: str,
    canonical_name: str,
    truth: TemporalTruth,
    status: str = "verified",
    confidence: Decimal = Decimal("1"),
    valid_to: datetime | None = None,
    source_manifest_id: uuid.UUID | None = None,
    provenance: dict[str, Any] | None = None,
) -> tuple[EconomicEntity, bool]:
    if entity_type not in ENTITY_TYPES:
        raise ValueError(f"unsupported entity type: {entity_type}")
    if status not in VALID_ENTITY_STATUSES:
        raise ValueError(f"unsupported entity status: {status}")
    normalized = normalize_name(canonical_name)
    existing = session.scalar(
        select(EconomicEntity).where(
            EconomicEntity.workspace_id == workspace_id,
            EconomicEntity.entity_type == entity_type,
            EconomicEntity.normalized_name == normalized,
        )
    )
    if existing is not None:
        return existing, False
    item = EconomicEntity(
        workspace_id=workspace_id,
        entity_type=entity_type,
        canonical_name=canonical_name.strip(),
        normalized_name=normalized,
        status=status,
        valid_from=truth.effective_time,
        valid_to=valid_to,
        first_seen=truth.retrieval_time,
        last_verified=truth.retrieval_time,
        event_time=truth.event_time,
        observation_time=truth.observation_time,
        publication_time=truth.publication_time,
        retrieval_time=truth.retrieval_time,
        effective_time=truth.effective_time,
        revision_time=truth.revision_time,
        simulation_eligible_time=truth.simulation_eligible_time,
        time_precision=truth.precision,
        source_time_zone=truth.source_time_zone,
        confidence=confidence,
        source_manifest_id=source_manifest_id,
        provenance_json=provenance or {},
    )
    session.add(item)
    session.flush()
    return item, True


def add_alias(
    session: Session,
    entity: EconomicEntity,
    alias: str,
    *,
    source: str,
    simulation_eligible_time: datetime,
) -> tuple[EntityAlias, bool]:
    normalized = normalize_name(alias)
    existing = session.scalar(
        select(EntityAlias).where(
            EntityAlias.entity_id == entity.id,
            EntityAlias.normalized_alias == normalized,
        )
    )
    if existing is not None:
        return existing, False
    item = EntityAlias(
        workspace_id=entity.workspace_id,
        entity_id=entity.id,
        alias=alias.strip(),
        normalized_alias=normalized,
        source=source,
        valid_from=simulation_eligible_time,
        simulation_eligible_time=simulation_eligible_time,
    )
    session.add(item)
    session.flush()
    return item, True


def attach_identifier(
    session: Session,
    entity: EconomicEntity,
    *,
    namespace: str,
    value: str,
    method: str,
    confidence: Decimal,
    source: str,
    resolver_version: str,
    resolved_at: datetime,
    valid_from: datetime,
    simulation_eligible_time: datetime,
    evidence_reference: str | None = None,
) -> EntityIdentifier | EntityResolutionCandidate:
    normalized = normalize_identifier(namespace, value)
    existing = session.scalar(
        select(EntityIdentifier).where(
            EntityIdentifier.workspace_id == entity.workspace_id,
            EntityIdentifier.namespace == namespace,
            EntityIdentifier.normalized_value == normalized,
        )
    )
    if existing is not None:
        if existing.entity_id == entity.id:
            return existing
        candidate = create_resolution_candidate(
            session,
            entity,
            namespace=namespace,
            value=value,
            method=method,
            confidence=confidence,
            source=source,
            resolver_version=resolver_version,
            resolved_at=resolved_at,
            valid_from=valid_from,
            simulation_eligible_time=simulation_eligible_time,
            status="ambiguous",
            evidence={"conflicts_with_entity_id": str(existing.entity_id)},
        )
        session.add(
            GraphQualityIssue(
                workspace_id=entity.workspace_id,
                issue_type="ambiguous_identifier",
                entity_id=entity.id,
                details={"namespace": namespace, "normalized_value": normalized},
            )
        )
        session.flush()
        return candidate
    item = EntityIdentifier(
        workspace_id=entity.workspace_id,
        entity_id=entity.id,
        namespace=namespace,
        value=value,
        normalized_value=normalized,
        mapping_method=method,
        confidence=confidence,
        source=source,
        evidence_reference=evidence_reference,
        resolver_version=resolver_version,
        resolved_at=resolved_at,
        valid_from=valid_from,
        simulation_eligible_time=simulation_eligible_time,
    )
    session.add(item)
    session.flush()
    return item


def create_resolution_candidate(
    session: Session,
    entity: EconomicEntity,
    *,
    namespace: str,
    value: str,
    method: str,
    confidence: Decimal,
    source: str,
    resolver_version: str,
    resolved_at: datetime,
    valid_from: datetime,
    simulation_eligible_time: datetime,
    status: str = "candidate",
    evidence: dict[str, Any] | None = None,
) -> EntityResolutionCandidate:
    normalized = normalize_identifier(namespace, value)
    existing = session.scalar(
        select(EntityResolutionCandidate).where(
            EntityResolutionCandidate.workspace_id == entity.workspace_id,
            EntityResolutionCandidate.namespace == namespace,
            EntityResolutionCandidate.normalized_value == normalized,
            EntityResolutionCandidate.candidate_entity_id == entity.id,
        )
    )
    if existing is not None:
        return existing
    item = EntityResolutionCandidate(
        workspace_id=entity.workspace_id,
        namespace=namespace,
        value=value,
        normalized_value=normalized,
        candidate_entity_id=entity.id,
        method=method,
        confidence=confidence,
        source=source,
        evidence_json=evidence or {},
        resolver_version=resolver_version,
        status=status,
        resolved_at=resolved_at,
        valid_from=valid_from,
        simulation_eligible_time=simulation_eligible_time,
    )
    session.add(item)
    session.flush()
    return item


def decide_resolution(
    session: Session,
    candidate: EntityResolutionCandidate,
    *,
    decision: str,
    reason: str,
    user_id: uuid.UUID,
) -> EntityResolutionDecision:
    if decision not in {"confirmed", "rejected"}:
        raise ValueError("resolution decision must be confirmed or rejected")
    if candidate.status in {"confirmed", "rejected"}:
        existing = session.scalar(
            select(EntityResolutionDecision).where(
                EntityResolutionDecision.candidate_id == candidate.id
            )
        )
        if existing is None or existing.decision != decision:
            raise ValueError("resolution candidate already has a different final decision")
        return existing
    if decision == "confirmed":
        conflict = session.scalar(
            select(EntityIdentifier).where(
                EntityIdentifier.workspace_id == candidate.workspace_id,
                EntityIdentifier.namespace == candidate.namespace,
                EntityIdentifier.normalized_value == candidate.normalized_value,
            )
        )
        if conflict is not None and conflict.entity_id != candidate.candidate_entity_id:
            raise ValueError(
                "identifier remains mapped to a different entity; resolve conflict first"
            )
        if conflict is None:
            session.add(
                EntityIdentifier(
                    workspace_id=candidate.workspace_id,
                    entity_id=candidate.candidate_entity_id,
                    namespace=candidate.namespace,
                    value=candidate.value,
                    normalized_value=candidate.normalized_value,
                    mapping_method="manual_confirmation",
                    confidence=candidate.confidence,
                    source=candidate.source,
                    evidence_reference=None,
                    resolver_version=candidate.resolver_version,
                    resolved_at=datetime.now(UTC),
                    valid_from=candidate.valid_from,
                    valid_to=candidate.valid_to,
                    simulation_eligible_time=candidate.simulation_eligible_time,
                )
            )
    candidate.status = decision
    item = EntityResolutionDecision(
        workspace_id=candidate.workspace_id,
        candidate_id=candidate.id,
        decision=decision,
        reason=reason,
        decided_by_user_id=user_id,
    )
    session.add(item)
    session.flush()
    return item


def create_evidence(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    source_record_identifier: str,
    publication_time: datetime,
    simulation_eligible_time: datetime,
    evidence_type: str,
    checksum: str,
    parser_version: str,
    confidence: Decimal,
    source_manifest_id: uuid.UUID | None = None,
    sec_filing_id: uuid.UUID | None = None,
    source_entity_id: uuid.UUID | None = None,
    structured_payload: dict[str, Any] | None = None,
    content_reference: str | None = None,
    supporting_text: str | None = None,
) -> tuple[EvidenceRecord, bool]:
    if not re.fullmatch(r"[0-9a-f]{64}", checksum):
        raise ValueError("evidence checksum must be lowercase SHA-256")
    if simulation_eligible_time < publication_time:
        raise ValueError("evidence eligibility cannot precede publication")
    existing = session.scalar(
        select(EvidenceRecord).where(
            EvidenceRecord.workspace_id == workspace_id,
            EvidenceRecord.checksum == checksum,
            EvidenceRecord.source_record_identifier == source_record_identifier,
        )
    )
    if existing is not None:
        return existing, False
    item = EvidenceRecord(
        workspace_id=workspace_id,
        source_manifest_id=source_manifest_id,
        sec_filing_id=sec_filing_id,
        source_record_identifier=source_record_identifier,
        source_entity_id=source_entity_id,
        publication_time=publication_time,
        simulation_eligible_time=simulation_eligible_time,
        evidence_type=evidence_type,
        structured_payload=structured_payload or {},
        content_reference=content_reference,
        supporting_text=supporting_text,
        checksum=checksum,
        parser_version=parser_version,
        confidence=confidence,
    )
    session.add(item)
    session.flush()
    return item, True


def create_relationship(
    session: Session,
    *,
    subject: EconomicEntity,
    predicate: str,
    object_entity: EconomicEntity,
    valid_from: datetime,
    simulation_eligible_time: datetime,
    method: str,
    method_version: str,
    components: dict[str, Decimal],
    evidence: list[tuple[EvidenceRecord, str, Decimal]],
    status: str = "verified",
    strength: Decimal | None = None,
    valid_to: datetime | None = None,
    provenance: dict[str, Any] | None = None,
) -> tuple[EconomicRelationship, bool]:
    if subject.workspace_id != object_entity.workspace_id:
        raise ValueError("cross-workspace relationships are forbidden")
    if subject.id == object_entity.id:
        raise ValueError("self relationships are forbidden")
    if predicate not in RELATIONSHIP_TYPES:
        raise ValueError(f"unsupported relationship type: {predicate}")
    if status not in VALID_RELATIONSHIP_STATUSES:
        raise ValueError(f"unsupported relationship status: {status}")
    supporting = [item for item in evidence if item[1] == "supporting"]
    if status == "verified" and not supporting:
        raise ValueError("verified relationships require supporting evidence")
    evidence_floor = max(
        (item[0].simulation_eligible_time for item in supporting),
        default=simulation_eligible_time,
    )
    if simulation_eligible_time < evidence_floor:
        raise ValueError("relationship eligibility cannot precede supporting evidence")
    confidence = aggregate_confidence(components)
    existing = session.scalar(
        select(EconomicRelationship).where(
            EconomicRelationship.workspace_id == subject.workspace_id,
            EconomicRelationship.subject_entity_id == subject.id,
            EconomicRelationship.predicate == predicate,
            EconomicRelationship.object_entity_id == object_entity.id,
            EconomicRelationship.valid_from == valid_from,
        )
    )
    if existing is not None:
        return existing, False
    item = EconomicRelationship(
        workspace_id=subject.workspace_id,
        subject_entity_id=subject.id,
        predicate=predicate,
        object_entity_id=object_entity.id,
        confidence=confidence,
        strength=strength,
        valid_from=valid_from,
        valid_to=valid_to,
        discovered_at=simulation_eligible_time,
        last_verified_at=simulation_eligible_time,
        simulation_eligible_time=simulation_eligible_time,
        method=method,
        method_version=method_version,
        provenance_json=provenance or {},
        status=status,
    )
    session.add(item)
    session.flush()
    for component, value in components.items():
        session.add(
            RelationshipConfidenceComponent(
                workspace_id=subject.workspace_id,
                relationship_id=item.id,
                formula_version=CONFIDENCE_FORMULA_VERSION,
                component=component,
                value=value,
                rationale=f"Deterministic {component.replace('_', ' ')} input",
            )
        )
    for record, direction, weight in evidence:
        if direction not in {"supporting", "contradicting"}:
            raise ValueError("evidence direction must be supporting or contradicting")
        session.add(
            RelationshipEvidence(
                workspace_id=subject.workspace_id,
                relationship_id=item.id,
                evidence_id=record.id,
                direction=direction,
                weight=weight,
            )
        )
    session.flush()
    return item, True


def expire_relationship(
    relationship: EconomicRelationship, *, valid_to: datetime
) -> EconomicRelationship:
    if valid_to <= relationship.valid_from:
        raise ValueError("relationship expiry must follow valid_from")
    relationship.valid_to = valid_to
    relationship.status = "expired"
    session = object_session(relationship)
    if session is not None:
        session.flush()
    return relationship


def queue_recompute(
    session: Session,
    *,
    company: EconomicEntity,
    trigger_reason: str,
    idempotency_key: str,
) -> tuple[GraphRecomputeJob, bool]:
    existing = session.scalar(
        select(GraphRecomputeJob).where(
            GraphRecomputeJob.workspace_id == company.workspace_id,
            GraphRecomputeJob.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing, False
    item = GraphRecomputeJob(
        workspace_id=company.workspace_id,
        company_entity_id=company.id,
        trigger_reason=trigger_reason,
        idempotency_key=idempotency_key,
    )
    session.add(item)
    session.flush()
    return item, True


def evidence_counts(session: Session, relationship_id: uuid.UUID) -> dict[str, int]:
    rows = session.execute(
        select(RelationshipEvidence.direction, func.count(RelationshipEvidence.id))
        .where(RelationshipEvidence.relationship_id == relationship_id)
        .group_by(RelationshipEvidence.direction)
    ).all()
    return {str(direction): int(count) for direction, count in rows}


def scan_graph_quality(
    session: Session, *, workspace_id: uuid.UUID, as_of: datetime
) -> list[GraphQualityIssue]:
    """Persist visible graph conflicts; never discard or auto-resolve them."""

    findings: list[tuple[str, uuid.UUID | None, uuid.UUID | None, dict[str, Any]]] = []
    entities = session.scalars(
        select(EconomicEntity).where(EconomicEntity.workspace_id == workspace_id)
    ).all()
    relationships = session.scalars(
        select(EconomicRelationship).where(EconomicRelationship.workspace_id == workspace_id)
    ).all()
    connected = {
        entity_id
        for relationship in relationships
        for entity_id in (relationship.subject_entity_id, relationship.object_entity_id)
    }
    for entity in entities:
        if entity.id not in connected:
            findings.append(("orphan_entity", entity.id, None, {}))
    relationship_keys = {
        (item.subject_entity_id, item.predicate, item.object_entity_id): item
        for item in relationships
    }
    for relationship in relationships:
        counts = evidence_counts(session, relationship.id)
        if relationship.status == "verified" and counts.get("supporting", 0) == 0:
            findings.append(("missing_evidence", None, relationship.id, {}))
        if counts.get("supporting", 0) and counts.get("contradicting", 0):
            findings.append(("conflicting_evidence", None, relationship.id, counts))
        if relationship.confidence < Decimal("0.5"):
            findings.append(
                (
                    "low_confidence",
                    None,
                    relationship.id,
                    {"confidence": str(relationship.confidence)},
                )
            )
        if relationship.valid_to is not None and relationship.valid_to <= as_of:
            findings.append(("expired_relationship", None, relationship.id, {}))
        reverse = relationship_keys.get(
            (relationship.object_entity_id, relationship.predicate, relationship.subject_entity_id)
        )
        if reverse is not None and relationship.predicate in {"OWNS", "HAS_SEGMENT"}:
            findings.append(
                (
                    "cycle_anomaly",
                    None,
                    relationship.id,
                    {"reverse_relationship_id": str(reverse.id)},
                )
            )
    persisted: list[GraphQualityIssue] = []
    for issue_type, entity_id, relationship_id, details in findings:
        existing = session.scalar(
            select(GraphQualityIssue).where(
                GraphQualityIssue.workspace_id == workspace_id,
                GraphQualityIssue.issue_type == issue_type,
                GraphQualityIssue.entity_id == entity_id,
                GraphQualityIssue.relationship_id == relationship_id,
                GraphQualityIssue.status.in_(("open", "acknowledged")),
            )
        )
        if existing is not None:
            persisted.append(existing)
            continue
        issue = GraphQualityIssue(
            workspace_id=workspace_id,
            issue_type=issue_type,
            entity_id=entity_id,
            relationship_id=relationship_id,
            details=details,
        )
        session.add(issue)
        persisted.append(issue)
    session.flush()
    return persisted
