from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db
from apps.api.schemas import DataSourceResponse, SystemInfoResponse
from packages.database.models import Asset, DataSource, PriceBar, Watchlist

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/info", response_model=SystemInfoResponse)
def system_info(request: Request, session: Session = Depends(get_db)) -> SystemInfoResponse:
    session.execute(text("SELECT 1"))
    public = request.app.state.settings.public_summary()
    return SystemInfoResponse(
        **public,
        database_health="healthy",
        tracked_assets=session.scalar(select(func.count(Asset.id))) or 0,
        watchlists=session.scalar(select(func.count(Watchlist.id))) or 0,
        demonstration_bars=session.scalar(
            select(func.count(PriceBar.id)).where(PriceBar.is_demonstration_data.is_(True))
        )
        or 0,
        warning="Synthetic demonstration data — not live market data.",
    )


@router.get("/data-sources", response_model=list[DataSourceResponse])
def data_sources(session: Session = Depends(get_db)) -> list[DataSourceResponse]:
    sources = session.scalars(select(DataSource).order_by(DataSource.name)).all()
    return [
        DataSourceResponse(
            id=source.id,
            name=source.name,
            provider_type=source.provider_type,
            is_enabled=source.is_enabled,
            health=source.health,
            last_successful_retrieval=source.last_successful_retrieval,
            stored_records=session.scalar(
                select(func.count(PriceBar.id)).where(PriceBar.data_source_id == source.id)
            )
            or 0,
            freshness_status="fixed demonstration snapshot"
            if source.provider_type == "synthetic"
            else "unknown",
            license_notes=source.license_notes,
        )
        for source in sources
    ]
