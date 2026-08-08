from __future__ import annotations

import hashlib
import json
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from packages.database.models import EconomicEntity, SecCompany, SecFiling
from packages.economic_graph.confidence import CONFIDENCE_WEIGHTS
from packages.economic_graph.service import (
    attach_identifier,
    create_entity,
    create_evidence,
    create_relationship,
)
from packages.world_data.temporal import TemporalTruth


def _truth(filing: SecFiling) -> TemporalTruth:
    return TemporalTruth(
        event_time=filing.accepted_at,
        observation_time=filing.accepted_at,
        publication_time=filing.accepted_at,
        retrieval_time=filing.retrieved_at,
        effective_time=filing.accepted_at,
        revision_time=filing.accepted_at,
        simulation_eligible_time=filing.simulation_eligible_at,
        precision="second",
    )


def _components() -> dict[str, Decimal]:
    values = {name: Decimal("0.95") for name in CONFIDENCE_WEIGHTS}
    values["extraction_confidence"] = Decimal("0.90")
    return values


def extract_structured_sec_graph(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    company: SecCompany,
    filing: SecFiling,
    structured: dict[str, list[str]],
) -> EconomicEntity:
    """Create only identity, security, subsidiary, segment, and geography links."""

    truth = _truth(filing)
    company_entity, _ = create_entity(
        session,
        workspace_id=workspace_id,
        entity_type="Company",
        canonical_name=company.name,
        truth=truth,
        confidence=Decimal("0.98"),
        provenance={"sec_company_id": str(company.id), "accession": filing.accession_number},
    )
    attach_identifier(
        session,
        company_entity,
        namespace="cik",
        value=company.cik,
        method="sec_exact",
        confidence=Decimal("1"),
        source="SEC submissions",
        resolver_version="sec-graph-v1",
        resolved_at=filing.retrieved_at,
        valid_from=filing.accepted_at,
        simulation_eligible_time=filing.simulation_eligible_at,
        evidence_reference=filing.accession_number,
    )
    for ticker in company.tickers:
        security, _ = create_entity(
            session,
            workspace_id=workspace_id,
            entity_type="Security",
            canonical_name=f"{ticker} common equity",
            truth=truth,
            provenance={"sec_company_id": str(company.id)},
        )
        attach_identifier(
            session,
            security,
            namespace="ticker",
            value=ticker,
            method="sec_exact",
            confidence=Decimal("0.98"),
            source="SEC submissions",
            resolver_version="sec-graph-v1",
            resolved_at=filing.retrieved_at,
            valid_from=filing.accepted_at,
            simulation_eligible_time=filing.simulation_eligible_at,
            evidence_reference=filing.accession_number,
        )
        _link_sec_item(session, company_entity, security, "HAS_SECURITY", filing, truth)
    mappings = {
        "subsidiaries": ("Subsidiary", "OWNS"),
        "segments": ("BusinessSegment", "HAS_SEGMENT"),
        "regions": ("Region", "LOCATED_IN"),
    }
    for key, (entity_type, predicate) in mappings.items():
        for name in sorted(set(structured.get(key, []))):
            target, _ = create_entity(
                session,
                workspace_id=workspace_id,
                entity_type=entity_type,
                canonical_name=name,
                truth=truth,
                provenance={"accession": filing.accession_number, "structured_field": key},
            )
            _link_sec_item(session, company_entity, target, predicate, filing, truth)
    return company_entity


def _link_sec_item(
    session: Session,
    company: EconomicEntity,
    target: EconomicEntity,
    predicate: str,
    filing: SecFiling,
    truth: TemporalTruth,
) -> None:
    payload = {
        "accession": filing.accession_number,
        "predicate": predicate,
        "subject": company.canonical_name,
        "object": target.canonical_name,
    }
    checksum = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    evidence, _ = create_evidence(
        session,
        workspace_id=company.workspace_id,
        source_record_identifier=f"{filing.accession_number}:{predicate}:{target.normalized_name}",
        publication_time=filing.accepted_at,
        simulation_eligible_time=filing.simulation_eligible_at,
        evidence_type="sec_structured_record",
        checksum=checksum,
        parser_version="sec-graph-v1",
        confidence=Decimal("0.95"),
        sec_filing_id=filing.id,
        source_entity_id=company.id,
        structured_payload=payload,
        content_reference=filing.raw_document_reference,
    )
    create_relationship(
        session,
        subject=company,
        predicate=predicate,
        object_entity=target,
        valid_from=truth.effective_time,
        simulation_eligible_time=truth.simulation_eligible_time,
        method="sec_structured_extraction",
        method_version="sec-graph-v1",
        components=_components(),
        evidence=[(evidence, "supporting", Decimal("1"))],
        provenance={"accession": filing.accession_number},
    )
