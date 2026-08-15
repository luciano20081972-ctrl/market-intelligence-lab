from __future__ import annotations

import hashlib
import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db, get_workspace_context
from packages.analytics.quantstats_adapter import (
    QuantStatsAnalyticsAdapter,
    canonical_metrics,
    reconcile_metrics,
)
from packages.database.models import AnalyticsComparisonRecord
from packages.security import WorkspaceContext

router = APIRouter(prefix="/analytics", tags=["portfolio analytics"])


class AnalyticsRequest(BaseModel):
    returns: list[float] = Field(min_length=2, max_length=5000)
    benchmark_returns: list[float] | None = Field(default=None, max_length=5000)
    period_start: date
    period_end: date
    benchmark: str | None = Field(default=None, max_length=32)
    tolerance: float = Field(default=1e-9, ge=0, le=1)


@router.post("/compare", status_code=status.HTTP_201_CREATED)
def compare_analytics(
    payload: AnalyticsRequest,
    context: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    if payload.period_end <= payload.period_start:
        raise HTTPException(status_code=422, detail="Analytics period is invalid")
    adapter = QuantStatsAnalyticsAdapter()
    values = tuple(payload.returns)
    benchmark = tuple(payload.benchmark_returns) if payload.benchmark_returns is not None else None
    try:
        canonical = canonical_metrics(values)
        external = adapter.calculate(values, benchmark)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    reconciliation = reconcile_metrics(canonical, external, tolerance=payload.tolerance)
    status_value = (
        "agrees"
        if all(item["agreement_status"] in {"agrees", "not_comparable"} for item in reconciliation)
        else "differs"
    )
    checksum = hashlib.sha256(
        json.dumps({"returns": payload.returns, "benchmark": payload.benchmark_returns}).encode()
    ).hexdigest()
    record = AnalyticsComparisonRecord(
        workspace_id=context.workspace_id,
        return_series_checksum=checksum,
        benchmark=payload.benchmark,
        period_start=payload.period_start,
        period_end=payload.period_end,
        canonical_metrics=canonical,
        adapter_metrics=external,
        reconciliation=reconciliation,
        methodology_notes=[
            "Canonical and adapter values use aligned daily return-series methodology",
            "Trade-level win rate is not compared with return-series win rate",
        ],
        engine_versions={
            "canonical": "mil-0.13.0",
            "quantstats": adapter.health().version.library_version or "unavailable",
        },
        agreement_status=status_value,
    )
    session.add(record)
    session.commit()
    return {
        "id": record.id,
        "canonical_metrics": canonical,
        "quantstats_metrics": external,
        "reconciliation": reconciliation,
        "agreement_status": status_value,
        "engine_versions": record.engine_versions,
        "return_series_checksum": checksum,
    }
