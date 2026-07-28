from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from apps.api.dependencies import get_db
from apps.api.schemas import (
    WatchlistAssetCreate,
    WatchlistCreate,
    WatchlistResponse,
    WatchlistUpdate,
)
from apps.api.serializers import serialize_watchlist
from packages.core.time import utc_now
from packages.database.models import Asset, Watchlist, WatchlistAsset
from packages.provenance import record_audit_event

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


def _find_watchlist(session: Session, watchlist_id: UUID) -> Watchlist:
    watchlist = session.scalar(
        select(Watchlist)
        .where(Watchlist.id == watchlist_id)
        .options(selectinload(Watchlist.asset_links).selectinload(WatchlistAsset.asset))
        .execution_options(populate_existing=True)
    )
    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist was not found")
    return watchlist


def _commit_or_conflict(session: Session, message: str) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=message) from exc


@router.get("", response_model=list[WatchlistResponse])
def list_watchlists(session: Session = Depends(get_db)) -> list[WatchlistResponse]:
    watchlists = session.scalars(
        select(Watchlist)
        .options(selectinload(Watchlist.asset_links).selectinload(WatchlistAsset.asset))
        .order_by(Watchlist.name)
    ).all()
    return [serialize_watchlist(session, watchlist) for watchlist in watchlists]


@router.post("", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
def create_watchlist(
    payload: WatchlistCreate, session: Session = Depends(get_db)
) -> WatchlistResponse:
    watchlist = Watchlist(name=payload.name, description=payload.description)
    try:
        session.add(watchlist)
        session.flush()
        record_audit_event(
            session,
            action="watchlist.created",
            entity_type="watchlist",
            entity_id=watchlist.id,
            details={"name": watchlist.name},
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="A watchlist with that name already exists"
        ) from exc
    return serialize_watchlist(session, _find_watchlist(session, watchlist.id))


@router.get("/{watchlist_id}", response_model=WatchlistResponse)
def get_watchlist(watchlist_id: UUID, session: Session = Depends(get_db)) -> WatchlistResponse:
    return serialize_watchlist(session, _find_watchlist(session, watchlist_id))


@router.patch("/{watchlist_id}", response_model=WatchlistResponse)
def update_watchlist(
    watchlist_id: UUID, payload: WatchlistUpdate, session: Session = Depends(get_db)
) -> WatchlistResponse:
    watchlist = _find_watchlist(session, watchlist_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(watchlist, field, value)
    watchlist.updated_at = utc_now()
    record_audit_event(
        session,
        action="watchlist.updated",
        entity_type="watchlist",
        entity_id=watchlist.id,
        details={"fields": sorted(changes)},
    )
    _commit_or_conflict(session, "A watchlist with that name already exists")
    return serialize_watchlist(session, _find_watchlist(session, watchlist.id))


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist(watchlist_id: UUID, session: Session = Depends(get_db)) -> Response:
    watchlist = _find_watchlist(session, watchlist_id)
    deleted_id = watchlist.id
    deleted_name = watchlist.name
    session.delete(watchlist)
    record_audit_event(
        session,
        action="watchlist.deleted",
        entity_type="watchlist",
        entity_id=deleted_id,
        details={"name": deleted_name},
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{watchlist_id}/assets", response_model=WatchlistResponse)
def add_asset(
    watchlist_id: UUID, payload: WatchlistAssetCreate, session: Session = Depends(get_db)
) -> WatchlistResponse:
    watchlist = _find_watchlist(session, watchlist_id)
    asset = session.scalar(select(Asset).where(Asset.symbol == payload.symbol))
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Asset '{payload.symbol}' was not found")
    try:
        session.add(WatchlistAsset(watchlist_id=watchlist.id, asset_id=asset.id))
        session.flush()
        record_audit_event(
            session,
            action="watchlist.asset_added",
            entity_type="watchlist",
            entity_id=watchlist.id,
            details={"symbol": asset.symbol},
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409, detail=f"Asset '{asset.symbol}' is already in this watchlist"
        ) from exc
    return serialize_watchlist(session, _find_watchlist(session, watchlist.id))


@router.delete("/{watchlist_id}/assets/{symbol}", response_model=WatchlistResponse)
def remove_asset(
    watchlist_id: UUID, symbol: str, session: Session = Depends(get_db)
) -> WatchlistResponse:
    watchlist = _find_watchlist(session, watchlist_id)
    normalized = symbol.strip().upper()
    asset = session.scalar(select(Asset).where(Asset.symbol == normalized))
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Asset '{normalized}' was not found")
    link = session.scalar(
        select(WatchlistAsset).where(
            WatchlistAsset.watchlist_id == watchlist.id, WatchlistAsset.asset_id == asset.id
        )
    )
    if link is None:
        raise HTTPException(
            status_code=404, detail=f"Asset '{normalized}' is not in this watchlist"
        )
    session.delete(link)
    record_audit_event(
        session,
        action="watchlist.asset_removed",
        entity_type="watchlist",
        entity_id=watchlist.id,
        details={"symbol": normalized},
    )
    session.commit()
    return serialize_watchlist(session, _find_watchlist(session, watchlist.id))
