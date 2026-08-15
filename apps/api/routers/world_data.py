from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db
from packages.database.models import (
    DataManifest,
    EnergyObservation,
    EnergySeries,
    MacroObservation,
    MacroSeries,
)
from packages.world_data.registry import DatasetDefinition, load_dataset_registry

router = APIRouter(tags=["world-data"])


def _dataset(item: DatasetDefinition) -> dict[str, Any]:
    return {
        "id": item.id,
        "provider": item.provider,
        "title": item.title,
        "transport": item.transport,
        "official_url": str(item.official_url),
        "expected_frequency": item.expected_frequency,
        "license": item.license,
        "temporal_mode": item.temporal_mode,
        "configured": True,
    }


@router.get("/data-sources")
def data_sources() -> list[dict[str, Any]]:
    return [_dataset(item) for item in load_dataset_registry().datasets]


@router.get("/data-sources/{dataset_id}/health")
def data_source_health(dataset_id: str, session: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        definition = load_dataset_registry().get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Data source not found") from exc
    latest = session.scalars(
        select(DataManifest)
        .where(DataManifest.dataset_id == dataset_id)
        .order_by(DataManifest.retrieval_time.desc())
        .limit(1)
    ).first()
    return {
        **_dataset(definition),
        "fixture_verified": True,
        "live_verified": latest is not None,
        "last_retrieval": latest.retrieval_time if latest else None,
        "freshness": "never-imported" if latest is None else "available",
        "lag_seconds": None,
        "record_count": latest.record_count if latest else 0,
        "latest_manifest_id": str(latest.id) if latest else None,
        "coverage_start": latest.temporal_coverage_start if latest else None,
        "coverage_end": latest.temporal_coverage_end if latest else None,
    }


@router.get("/data-sources/{dataset_id}")
def data_source(dataset_id: str) -> dict[str, Any]:
    try:
        return _dataset(load_dataset_registry().get(dataset_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Data source not found") from exc


def _manifest(item: DataManifest) -> dict[str, Any]:
    return {column.name: getattr(item, column.name) for column in DataManifest.__table__.columns}


@router.get("/data-manifests")
def data_manifests(
    dataset_id: str | None = None, session: Session = Depends(get_db)
) -> dict[str, Any]:
    query = select(DataManifest).order_by(DataManifest.retrieval_time.desc())
    if dataset_id:
        query = query.where(DataManifest.dataset_id == dataset_id)
    items = session.scalars(query.limit(200)).all()
    return {"items": [_manifest(item) for item in items], "total": len(items)}


@router.get("/data-manifests/{manifest_id}")
def data_manifest(manifest_id: uuid.UUID, session: Session = Depends(get_db)) -> dict[str, Any]:
    item = session.get(DataManifest, manifest_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Data manifest not found")
    return _manifest(item)


def _series(item: MacroSeries | EnergySeries) -> dict[str, Any]:
    return {column.name: getattr(item, column.name) for column in item.__table__.columns}


def _observation(item: MacroObservation | EnergyObservation) -> dict[str, Any]:
    return {column.name: getattr(item, column.name) for column in item.__table__.columns}


@router.get("/macro/series")
def macro_series(session: Session = Depends(get_db)) -> dict[str, Any]:
    items = session.scalars(select(MacroSeries).order_by(MacroSeries.external_id)).all()
    return {"items": [_series(item) for item in items], "total": len(items)}


@router.get("/macro/series/{series_id}")
def macro_series_detail(series_id: uuid.UUID, session: Session = Depends(get_db)) -> dict[str, Any]:
    item = session.get(MacroSeries, series_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Macro series not found")
    return _series(item)


@router.get("/macro/series/{series_id}/observations")
def macro_observations(series_id: uuid.UUID, session: Session = Depends(get_db)) -> dict[str, Any]:
    items = session.scalars(
        select(MacroObservation)
        .where(MacroObservation.series_id == series_id)
        .order_by(MacroObservation.observation_time, MacroObservation.revision_time)
    ).all()
    return {
        "items": [_observation(item) for item in items],
        "total": len(items),
        "label": "latest revised; use /as-of for point-in-time research",
    }


@router.get("/macro/series/{series_id}/as-of")
def macro_as_of(
    series_id: uuid.UUID,
    as_of: datetime = Query(),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    if as_of.tzinfo is None:
        raise HTTPException(status_code=422, detail="as_of must include a timezone")
    rows = session.scalars(
        select(MacroObservation)
        .where(
            MacroObservation.series_id == series_id,
            MacroObservation.simulation_eligible_time <= as_of,
        )
        .order_by(
            MacroObservation.observation_time,
            MacroObservation.revision_time.desc(),
        )
    ).all()
    latest_by_period: dict[datetime, MacroObservation] = {}
    for row in rows:
        latest_by_period.setdefault(row.observation_time, row)
    return {
        "items": [_observation(item) for item in latest_by_period.values()],
        "total": len(latest_by_period),
        "as_of": as_of,
        "point_in_time_safe": True,
    }


@router.get("/energy/series")
def energy_series(session: Session = Depends(get_db)) -> dict[str, Any]:
    items = session.scalars(select(EnergySeries).order_by(EnergySeries.external_id)).all()
    return {"items": [_series(item) for item in items], "total": len(items)}


@router.get("/energy/series/{series_id}/observations")
def energy_observations(series_id: uuid.UUID, session: Session = Depends(get_db)) -> dict[str, Any]:
    items = session.scalars(
        select(EnergyObservation)
        .where(EnergyObservation.series_id == series_id)
        .order_by(EnergyObservation.observation_time)
    ).all()
    return {"items": [_observation(item) for item in items], "total": len(items)}
