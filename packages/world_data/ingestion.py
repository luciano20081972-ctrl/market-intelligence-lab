from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database.models import (
    DataManifest,
    EnergyObservation,
    EnergySeries,
    IngestionCheckpoint,
    MacroObservation,
    MacroSeries,
)
from packages.world_data.manifests import SourceManifest


def persist_manifest(session: Session, manifest: SourceManifest) -> tuple[DataManifest, bool]:
    existing = session.scalars(
        select(DataManifest).where(
            DataManifest.source_id == manifest.source_id,
            DataManifest.dataset_id == manifest.dataset_id,
            DataManifest.checksum == manifest.checksum,
        )
    ).first()
    if existing is not None:
        return existing, False
    item = DataManifest(
        **manifest.model_dump(exclude={"job_id", "parent_manifest_id"}),
        job_id=uuid.UUID(manifest.job_id) if manifest.job_id else None,
        parent_manifest_id=(uuid.UUID(manifest.parent_manifest_id)
                            if manifest.parent_manifest_id else None),
    )
    session.add(item)
    session.flush()
    return item, True


def save_checkpoint(
    session: Session,
    source_id: str,
    dataset_id: str,
    cursor: dict[str, Any],
    manifest_id: uuid.UUID,
) -> IngestionCheckpoint:
    checkpoint = session.scalars(
        select(IngestionCheckpoint).where(
            IngestionCheckpoint.source_id == source_id,
            IngestionCheckpoint.dataset_id == dataset_id,
        )
    ).first()
    if checkpoint is None:
        checkpoint = IngestionCheckpoint(source_id=source_id, dataset_id=dataset_id)
        session.add(checkpoint)
    checkpoint.cursor_json = cursor
    checkpoint.last_manifest_id = manifest_id
    checkpoint.updated_at = datetime.now(UTC)
    session.flush()
    return checkpoint


def ingest_macro_rows(
    session: Session,
    series: MacroSeries,
    rows: list[dict[str, Any]],
    manifest_id: uuid.UUID,
) -> tuple[int, int]:
    inserted = skipped = 0
    session.add(series)
    session.flush()
    for row in rows:
        truth = row["truth"]
        duplicate = session.scalars(
            select(MacroObservation.id).where(
                MacroObservation.series_id == series.id,
                MacroObservation.observation_time == truth.observation_time,
                MacroObservation.revision_time == truth.revision_time,
                MacroObservation.source_value == row["source_value"],
            )
        ).first()
        if duplicate:
            skipped += 1
            continue
        session.add(MacroObservation(
            series_id=series.id, source_value=row["source_value"], numeric_value=row["value"],
            event_time=truth.event_time, observation_time=truth.observation_time,
            publication_time=truth.publication_time, retrieval_time=truth.retrieval_time,
            effective_time=truth.effective_time, revision_time=truth.revision_time,
            simulation_eligible_time=truth.simulation_eligible_time,
            realtime_end=(
                datetime.fromisoformat(row["realtime_end"]).replace(tzinfo=UTC)
                if row.get("realtime_end") and row["realtime_end"] != "9999-12-31"
                else None
            ),
            time_precision=truth.precision, source_time_zone=truth.source_time_zone,
            quality_flags=[flag.value for flag in truth.quality_flags], manifest_id=manifest_id,
        ))
        inserted += 1
    session.flush()
    return inserted, skipped


def ingest_energy_rows(
    session: Session,
    series: EnergySeries,
    rows: list[dict[str, Any]],
    manifest_id: uuid.UUID,
) -> tuple[int, int]:
    inserted = skipped = 0
    session.add(series)
    session.flush()
    for row in rows:
        truth = row["truth"]
        duplicate = session.scalars(
            select(EnergyObservation.id).where(
                EnergyObservation.series_id == series.id,
                EnergyObservation.observation_time == truth.observation_time,
                EnergyObservation.source_value == row["source_value"],
            )
        ).first()
        if duplicate:
            skipped += 1
            continue
        session.add(EnergyObservation(
            series_id=series.id, source_value=row["source_value"], numeric_value=row["value"],
            event_time=truth.event_time, observation_time=truth.observation_time,
            publication_time=truth.publication_time, retrieval_time=truth.retrieval_time,
            effective_time=truth.effective_time, revision_time=truth.revision_time,
            simulation_eligible_time=truth.simulation_eligible_time,
            time_precision=truth.precision, source_time_zone=truth.source_time_zone,
            quality_flags=[flag.value for flag in truth.quality_flags], manifest_id=manifest_id,
        ))
        inserted += 1
    session.flush()
    return inserted, skipped
