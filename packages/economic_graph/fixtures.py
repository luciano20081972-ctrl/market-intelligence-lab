from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database.models import CompanyDriverProfile, EconomicEntity
from packages.economic_graph.confidence import CONFIDENCE_WEIGHTS
from packages.economic_graph.profiles import generate_driver_profile, route_datasets
from packages.economic_graph.service import (
    attach_identifier,
    create_entity,
    create_evidence,
    create_relationship,
)
from packages.world_data.temporal import TemporalTruth

FIXTURE_TIME = datetime(2026, 1, 15, 12, tzinfo=UTC)

REFERENCE_COMPANIES: dict[str, dict[str, Any]] = {
    "semiconductor": {
        "name": "Silica Systems",
        "ticker": "SILI",
        "cik": "1000000001",
        "relationships": [
            ("USES_TECHNOLOGY", "Technology", "High-bandwidth memory"),
            ("EXPOSED_TO", "Country", "Taiwan"),
            ("CONSUMES", "EnergyMarket", "Industrial electricity"),
            ("DEPENDS_ON", "Supplier", "Advanced semiconductor foundry capacity"),
            ("REGULATED_BY", "Regulation", "Advanced computing export controls"),
        ],
    },
    "airline": {
        "name": "Meridian Air",
        "ticker": "MERA",
        "cik": "1000000002",
        "relationships": [
            ("DEPENDS_ON", "Commodity", "Jet fuel"),
            ("AFFECTED_BY", "Event", "Severe weather disruption"),
            ("OPERATES", "TransportationNode", "Metropolitan airport network"),
            ("DEPENDS_ON", "ResearchTopic", "Passenger travel demand"),
            ("DEPENDS_ON", "ResearchTopic", "Specialized aviation labor"),
        ],
    },
    "agriculture": {
        "name": "Harvest Fields Cooperative",
        "ticker": "HVST",
        "cik": "1000000003",
        "relationships": [
            ("AFFECTED_BY", "Event", "Drought and crop weather"),
            ("DEPENDS_ON", "Commodity", "Irrigation water"),
            ("USES", "Product", "Fertilizer and soil inputs"),
            ("PRODUCES", "Commodity", "Row crops"),
            ("CONSUMES", "EnergyMarket", "Agricultural energy"),
        ],
    },
}


def fixture_truth() -> TemporalTruth:
    return TemporalTruth(
        event_time=FIXTURE_TIME - timedelta(days=5),
        observation_time=FIXTURE_TIME - timedelta(days=5),
        publication_time=FIXTURE_TIME - timedelta(days=2),
        retrieval_time=FIXTURE_TIME,
        effective_time=FIXTURE_TIME - timedelta(days=5),
        revision_time=FIXTURE_TIME - timedelta(days=2),
        simulation_eligible_time=FIXTURE_TIME,
        precision="second",
    )


def fixture_confidence() -> dict[str, Decimal]:
    return {name: Decimal("0.90") for name in CONFIDENCE_WEIGHTS}


def seed_reference_graph(session: Session, workspace_id: uuid.UUID) -> dict[str, EconomicEntity]:
    truth = fixture_truth()
    result: dict[str, EconomicEntity] = {}
    for sector, definition in REFERENCE_COMPANIES.items():
        company, _ = create_entity(
            session,
            workspace_id=workspace_id,
            entity_type="Company",
            canonical_name=definition["name"],
            truth=truth,
            provenance={"reference_fixture": True, "sector": sector},
        )
        attach_identifier(
            session,
            company,
            namespace="ticker",
            value=definition["ticker"],
            method="fixture_exact",
            confidence=Decimal("1"),
            source="v0.8-reference-fixture",
            resolver_version="fixture-v1",
            resolved_at=FIXTURE_TIME,
            valid_from=truth.effective_time,
            simulation_eligible_time=truth.simulation_eligible_time,
        )
        attach_identifier(
            session,
            company,
            namespace="cik",
            value=definition["cik"],
            method="fixture_exact",
            confidence=Decimal("1"),
            source="v0.8-reference-fixture",
            resolver_version="fixture-v1",
            resolved_at=FIXTURE_TIME,
            valid_from=truth.effective_time,
            simulation_eligible_time=truth.simulation_eligible_time,
        )
        for index, (predicate, entity_type, name) in enumerate(definition["relationships"]):
            target, _ = create_entity(
                session,
                workspace_id=workspace_id,
                entity_type=entity_type,
                canonical_name=name,
                truth=truth,
                provenance={"reference_fixture": True},
            )
            source_id = f"reference:{sector}:{index}:{predicate}"
            checksum = hashlib.sha256(source_id.encode()).hexdigest()
            evidence, _ = create_evidence(
                session,
                workspace_id=workspace_id,
                source_record_identifier=source_id,
                publication_time=truth.publication_time,
                simulation_eligible_time=truth.simulation_eligible_time,
                evidence_type="structured_fixture",
                checksum=checksum,
                parser_version="reference-fixture-v1",
                confidence=Decimal("0.90"),
                structured_payload={
                    "company": definition["name"],
                    "predicate": predicate,
                    "object": name,
                },
            )
            create_relationship(
                session,
                subject=company,
                predicate=predicate,
                object_entity=target,
                valid_from=truth.effective_time,
                simulation_eligible_time=truth.simulation_eligible_time,
                method="deterministic_fixture",
                method_version="reference-fixture-v1",
                components=fixture_confidence(),
                evidence=[(evidence, "supporting", Decimal("1"))],
                provenance={"reference_fixture": True},
            )
        latest_profile = session.scalar(
            select(CompanyDriverProfile).where(
                CompanyDriverProfile.company_entity_id == company.id,
                CompanyDriverProfile.trigger_reason == "reference_fixture_seed",
            )
        )
        if latest_profile is None:
            latest_profile = generate_driver_profile(
                session,
                company=company,
                sector=sector,
                trigger_reason="reference_fixture_seed",
                generated_at=FIXTURE_TIME,
            )
            route_datasets(session, latest_profile)
        result[sector] = company
    session.flush()
    return result
