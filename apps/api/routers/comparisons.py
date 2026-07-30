from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db, get_principal, get_workspace_context
from packages.auth import AuthPrincipal
from packages.core.time import utc_now
from packages.database.models import Asset, Provider, ProviderComparison
from packages.market_data.comparison import compare_providers
from packages.provenance import record_audit_event
from packages.security import WorkspaceContext

router = APIRouter(prefix="/reconciliation/provider-comparisons", tags=["provider comparison"])


class ComparisonCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    primary_provider_id: UUID
    secondary_provider_id: UUID
    start_time: datetime
    end_time: datetime
    price_tolerance: Decimal = Field(default=Decimal("0.001"), ge=0, le=1)
    volume_tolerance: Decimal = Field(default=Decimal("0.05"), ge=0, le=1)


class ComparisonResolution(BaseModel):
    status: Literal["accepted primary", "accepted secondary", "excluded", "unresolved"]
    reason: str = Field(min_length=3, max_length=1000)


def _response(value: ProviderComparison) -> dict[str, object]:
    return {
        "id": value.id,
        "workspace_id": value.workspace_id,
        "asset_id": value.asset_id,
        "primary_provider_id": value.primary_provider_id,
        "secondary_provider_id": value.secondary_provider_id,
        "start_time": value.start_time,
        "end_time": value.end_time,
        "tolerances": value.tolerance_configuration,
        "summary": value.summary,
        "disagreements": value.disagreements,
        "resolution_status": value.resolution_status,
        "resolution_reason": value.resolution_reason,
        "compared_at": value.compared_at,
        "resolved_at": value.resolved_at,
    }


def _find(session: Session, comparison_id: UUID) -> ProviderComparison:
    value = session.get(ProviderComparison, comparison_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Provider comparison was not found")
    return value


@router.post("", status_code=status.HTTP_201_CREATED)
def create_comparison(
    payload: ComparisonCreate,
    context: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    asset = session.scalar(select(Asset).where(Asset.symbol == payload.symbol.strip().upper()))
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset was not found")
    if (
        session.get(Provider, payload.primary_provider_id) is None
        or session.get(Provider, payload.secondary_provider_id) is None
    ):
        raise HTTPException(status_code=404, detail="Provider was not found")
    try:
        comparison = compare_providers(
            session,
            workspace_id=context.workspace_id,
            asset=asset,
            primary_provider_id=payload.primary_provider_id,
            secondary_provider_id=payload.secondary_provider_id,
            start_time=payload.start_time,
            end_time=payload.end_time,
            price_tolerance=payload.price_tolerance,
            volume_tolerance=payload.volume_tolerance,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record_audit_event(
        session,
        action="provider_comparison.created",
        entity_type="provider_comparison",
        entity_id=comparison.id,
        details={"resolution_status": comparison.resolution_status},
    )
    session.commit()
    return _response(comparison)


@router.get("")
def list_comparisons(
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> dict[str, object]:
    total = session.scalar(select(func.count(ProviderComparison.id))) or 0
    values = session.scalars(
        select(ProviderComparison)
        .order_by(ProviderComparison.compared_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [_response(value) for value in values],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/{comparison_id}")
def get_comparison(comparison_id: UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    return _response(_find(session, comparison_id))


@router.post("/{comparison_id}/resolve")
def resolve_comparison(
    comparison_id: UUID,
    payload: ComparisonResolution,
    principal: AuthPrincipal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    value = _find(session, comparison_id)
    value.resolution_status = payload.status
    value.resolution_reason = payload.reason
    value.resolved_by_user_id = principal.user_id
    value.resolved_at = utc_now()
    record_audit_event(
        session,
        action="provider_comparison.resolved",
        entity_type="provider_comparison",
        entity_id=value.id,
        details={"resolution_status": payload.status},
    )
    session.commit()
    return _response(value)
