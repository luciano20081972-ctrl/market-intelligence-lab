from __future__ import annotations

import hashlib
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from packages.database.models import EconomicEntity, EnergySeries, MacroSeries
from packages.economic_graph.confidence import CONFIDENCE_WEIGHTS
from packages.economic_graph.service import (
    attach_identifier,
    create_entity,
    create_evidence,
    create_relationship,
)
from packages.world_data.temporal import TemporalTruth


def link_economic_series(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    context_entity: EconomicEntity,
    series: MacroSeries | EnergySeries,
    provider: str,
    truth: TemporalTruth,
) -> EconomicEntity:
    if context_entity.workspace_id != workspace_id:
        raise ValueError("context entity belongs to another workspace")
    series_entity, _ = create_entity(
        session,
        workspace_id=workspace_id,
        entity_type="EconomicSeries",
        canonical_name=f"{series.external_id} — {series.title}",
        truth=truth,
        provenance={"provider": provider, "series_id": series.external_id},
    )
    attach_identifier(
        session,
        series_entity,
        namespace="provider_series",
        value=f"{provider}:{series.external_id}",
        method="official_series_exact",
        confidence=Decimal("1"),
        source=provider,
        resolver_version="series-link-v1",
        resolved_at=truth.retrieval_time,
        valid_from=truth.effective_time,
        simulation_eligible_time=truth.simulation_eligible_time,
    )
    record_id = f"series-link:{context_entity.id}:{provider}:{series.external_id}"
    evidence, _ = create_evidence(
        session,
        workspace_id=workspace_id,
        source_record_identifier=record_id,
        publication_time=truth.publication_time,
        simulation_eligible_time=truth.simulation_eligible_time,
        evidence_type="official_series_metadata",
        checksum=hashlib.sha256(record_id.encode()).hexdigest(),
        parser_version="series-link-v1",
        confidence=Decimal("0.98"),
        structured_payload={
            "provider": provider,
            "series_id": series.external_id,
            "context_entity_id": str(context_entity.id),
        },
    )
    components = {name: Decimal("0.95") for name in CONFIDENCE_WEIGHTS}
    create_relationship(
        session,
        subject=context_entity,
        predicate="TRACKED_BY_SERIES",
        object_entity=series_entity,
        valid_from=truth.effective_time,
        simulation_eligible_time=truth.simulation_eligible_time,
        method="official_series_mapping",
        method_version="series-link-v1",
        components=components,
        evidence=[(evidence, "supporting", Decimal("1"))],
    )
    return series_entity
