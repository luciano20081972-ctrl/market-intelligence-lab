from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db, get_workspace_context
from packages.analytics import QuantStatsAnalyticsAdapter
from packages.database.models import ExternalEngineRun
from packages.external_engines import LeanAdapter, LeanBacktestRequest
from packages.optimization import SkfolioOptimizerAdapter
from packages.sec_intelligence import EdgarToolsSecAdapter, FixtureSecAdapter
from packages.security import WorkspaceContext
from packages.upstream import load_inventory

router = APIRouter(prefix="/upstream", tags=["upstream integrations"])


def _health_response(report: object) -> dict[str, object]:
    value = report
    return {
        "status": value.status,  # type: ignore[attr-defined]
        "available": value.available,  # type: ignore[attr-defined]
        "message": value.message,  # type: ignore[attr-defined]
        "version": {
            "project": value.version.project,  # type: ignore[attr-defined]
            "adapter_version": value.version.adapter_version,  # type: ignore[attr-defined]
            "library_version": value.version.library_version,  # type: ignore[attr-defined]
            "source_commit": value.version.source_commit,  # type: ignore[attr-defined]
        },
        "capabilities": [
            {
                "code": capability.code,
                "description": capability.description,
                "fixture_tested": capability.fixture_tested,
                "live_verified": capability.live_verified,
            }
            for capability in value.capabilities  # type: ignore[attr-defined]
        ],
    }


@router.get("/integrations")
def integrations(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    values = {
        "edgartools": _health_response(
            EdgarToolsSecAdapter(
                user_agent=settings.sec_user_agent,
                requests_per_second=settings.sec_requests_per_second,
                timeout_seconds=settings.sec_timeout_seconds,
            ).health()
        ),
        "sec_fixture": _health_response(FixtureSecAdapter().health()),
        "quantstats": _health_response(QuantStatsAnalyticsAdapter().health()),
        "skfolio": _health_response(SkfolioOptimizerAdapter().health()),
        "lean": _health_response(LeanAdapter(settings.lean_executable).health()),
    }
    return {"items": values, "contains_secrets": False}


@router.get("/licenses")
def license_inventory() -> dict[str, object]:
    inventory = load_inventory(Path("config/upstream-projects.yaml"))
    return {
        "items": inventory["projects"],
        "policy_version": inventory["policy_version"],
        "contains_source_code": False,
    }


@router.get("/engines/lean")
def lean_status(request: Request) -> dict[str, object]:
    return _health_response(LeanAdapter(request.app.state.settings.lean_executable).health())


class LeanFixtureRequest(BaseModel):
    strategy: str = "buy_and_hold"
    symbols: list[str] = Field(default_factory=lambda: ["AAPL"], min_length=1, max_length=2)
    start: date
    end: date
    initial_cash: Decimal = Field(default=Decimal("10000"), gt=0)
    fee_per_order: Decimal = Field(default=Decimal("1"), ge=0)
    slippage_bps: Decimal = Field(default=Decimal("5"), ge=0)
    live_mode: bool = False
    brokerage_credentials: dict[str, str] | None = None


@router.post("/engines/lean/fixture", status_code=status.HTTP_201_CREATED)
def lean_fixture(
    payload: LeanFixtureRequest,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    if payload.brokerage_credentials:
        raise HTTPException(status_code=422, detail="Brokerage credentials are forbidden")
    adapter = LeanAdapter(request.app.state.settings.lean_executable)
    try:
        result = adapter.fixture_run(
            LeanBacktestRequest(
                strategy=payload.strategy,
                symbols=tuple(symbol.upper() for symbol in payload.symbols),
                start=payload.start,
                end=payload.end,
                initial_cash=payload.initial_cash,
                fee_per_order=payload.fee_per_order,
                slippage_bps=payload.slippage_bps,
                live_mode=payload.live_mode,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    run = ExternalEngineRun(
        workspace_id=context.workspace_id,
        engine="lean",
        engine_version="optional-unavailable" if not adapter.health().available else "local",
        engine_commit=adapter.health().version.source_commit,
        request_checksum=result["request_checksum"],
        request_manifest={
            "strategy": payload.strategy,
            "symbols": payload.symbols,
            "start": payload.start.isoformat(),
            "end": payload.end.isoformat(),
            "live_mode": False,
        },
        result_manifest=result["manifest"],
        comparison=result["comparison"],
        status=result["status"],
        completed_at=None,
    )
    session.add(run)
    session.commit()
    return {"id": run.id, **result}
