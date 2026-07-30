from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db
from apps.api.schemas_sprint2 import (
    BacktestCreate,
    BacktestPage,
    BacktestSummaryResponse,
    BacktestTradeResponse,
    EquityPointResponse,
)
from packages.backtesting.service import run_backtest
from packages.backtesting.types import BacktestConfig
from packages.database.models import (
    BacktestDailySnapshot,
    BacktestReproducibilityManifest,
    BacktestRun,
    BacktestTrade,
    BacktestValidationReport,
    StrategyVersion,
)
from packages.provenance import record_audit_event
from packages.strategies.registry import get_strategy_definition, validate_strategy_parameters

router = APIRouter(prefix="/backtests", tags=["backtests"])


def _find_run(session: Session, run_id: UUID) -> BacktestRun:
    run = session.get(BacktestRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Backtest was not found")
    return run


def _summary(run: BacktestRun) -> BacktestSummaryResponse:
    strategy = run.strategy_version.strategy
    return BacktestSummaryResponse(
        id=run.id,
        strategy_version_id=run.strategy_version_id,
        strategy_name=strategy.name,
        strategy_type=strategy.strategy_type,
        status=run.status,
        asset_symbols=run.asset_symbols,
        benchmark_symbol=run.benchmark_symbol,
        start_time=run.start_time,
        end_time=run.end_time,
        initial_cash=run.initial_cash,
        final_equity=run.final_equity,
        cash_balance=run.cash_balance,
        metrics=run.metrics,
        strategy_configuration=run.strategy_configuration,
        risk_configuration=run.risk_configuration,
        execution_assumptions=run.execution_assumptions,
        data_source_identifiers=run.data_source_identifiers,
        application_version=run.application_version,
        is_hypothetical=run.is_hypothetical,
        data_classification=run.data_classification,
        provider_identifiers=run.provider_identifiers,
        import_job_identifiers=run.import_job_identifiers,
        adjustment_statuses=run.adjustment_statuses,
        calendar_code=run.calendar_code,
        created_at=run.created_at,
    )


@router.post("", response_model=BacktestSummaryResponse, status_code=status.HTTP_201_CREATED)
def create_backtest(
    payload: BacktestCreate,
    request: Request,
    session: Session = Depends(get_db),
) -> BacktestSummaryResponse:
    version = session.get(StrategyVersion, payload.strategy_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Strategy version was not found")
    try:
        parameters = validate_strategy_parameters(
            version.strategy.strategy_type, payload.parameters or version.parameters
        )
        get_strategy_definition(version.strategy.strategy_type)
        config = BacktestConfig(
            symbols=payload.symbols,
            benchmark_symbol=payload.benchmark_symbol,
            initial_cash=payload.initial_cash,
            commission=payload.commission,
            spread_bps=payload.spread_bps,
            slippage_bps=payload.slippage_bps,
            execution_delay=payload.execution_delay,
            max_position_pct=payload.max_position_pct,
            max_total_exposure=payload.max_total_exposure,
            data_source_mode=payload.data_source_mode,
            allow_mixed_data=payload.allow_mixed_data,
            adjustment_preference=payload.adjustment_preference,
        )
        run = run_backtest(
            session,
            strategy_version_id=version.id,
            parameters=parameters,
            config=config,
            start_time=payload.start_time,
            end_time=payload.end_time,
            settings=request.app.state.settings,
        )
        record_audit_event(
            session,
            action="backtest.completed",
            entity_type="backtest",
            entity_id=run.id,
            details={"strategy_version_id": str(version.id), "symbols": config.symbols},
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _summary(_find_run(session, run.id))


@router.get("", response_model=BacktestPage)
def list_backtests(
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    run_status: str | None = Query(default=None, alias="status"),
    sort_direction: Literal["asc", "desc"] = "desc",
) -> BacktestPage:
    filters = [BacktestRun.status == run_status] if run_status else []
    total = session.scalar(select(func.count(BacktestRun.id)).where(*filters)) or 0
    ordering = (
        asc(BacktestRun.created_at) if sort_direction == "asc" else desc(BacktestRun.created_at)
    )
    runs = session.scalars(
        select(BacktestRun)
        .where(*filters)
        .order_by(ordering)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return BacktestPage(
        items=[_summary(run) for run in runs],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{run_id}", response_model=BacktestSummaryResponse)
def get_backtest(run_id: UUID, session: Session = Depends(get_db)) -> BacktestSummaryResponse:
    return _summary(_find_run(session, run_id))


@router.get("/{run_id}/metrics", response_model=dict[str, object])
def get_metrics(run_id: UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    run = _find_run(session, run_id)
    return {**run.metrics, "hypothetical": True}


@router.get("/{run_id}/trades", response_model=list[BacktestTradeResponse])
def get_trades(
    run_id: UUID,
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    symbol: str | None = None,
) -> list[BacktestTradeResponse]:
    _find_run(session, run_id)
    filters = [BacktestTrade.backtest_run_id == run_id]
    if symbol:
        filters.append(BacktestTrade.symbol == symbol.strip().upper())
    trades = session.scalars(
        select(BacktestTrade)
        .where(*filters)
        .order_by(BacktestTrade.execution_time)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [
        BacktestTradeResponse(
            id=trade.id,
            symbol=trade.symbol,
            side=trade.side,
            signal_time=trade.signal_time,
            execution_time=trade.execution_time,
            quantity=trade.quantity,
            price=trade.price,
            gross_value=trade.gross_value,
            fees=trade.fees,
            cash_after=trade.cash_after,
            reason=trade.reason,
            source_price_bar_id=trade.source_price_bar_id,
        )
        for trade in trades
    ]


def _curve(session: Session, run_id: UUID) -> list[EquityPointResponse]:
    _find_run(session, run_id)
    snapshots = session.scalars(
        select(BacktestDailySnapshot)
        .where(BacktestDailySnapshot.backtest_run_id == run_id)
        .order_by(BacktestDailySnapshot.event_time)
    ).all()
    return [
        EquityPointResponse(
            event_time=snapshot.event_time,
            equity=snapshot.equity,
            benchmark_value=snapshot.benchmark_value,
            cash=snapshot.cash,
            exposure=snapshot.exposure,
            drawdown=snapshot.drawdown,
            cumulative_fees=snapshot.cumulative_fees,
        )
        for snapshot in snapshots
    ]


@router.get("/{run_id}/equity-curve", response_model=list[EquityPointResponse])
def get_equity_curve(run_id: UUID, session: Session = Depends(get_db)) -> list[EquityPointResponse]:
    return _curve(session, run_id)


@router.get("/{run_id}/drawdown", response_model=list[dict[str, object]])
def get_drawdown(run_id: UUID, session: Session = Depends(get_db)) -> list[dict[str, object]]:
    return [
        {"event_time": point.event_time, "drawdown": point.drawdown}
        for point in _curve(session, run_id)
    ]


@router.get("/{run_id}/manifest", response_model=dict[str, object])
def get_manifest(run_id: UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    _find_run(session, run_id)
    value = session.scalar(
        select(BacktestReproducibilityManifest).where(
            BacktestReproducibilityManifest.backtest_run_id == run_id
        )
    )
    if value is None:
        return {
            "backtest_run_id": str(run_id),
            "status": "legacy_unavailable",
            "manifest": {"unavailable": True},
        }
    return {
        "backtest_run_id": str(run_id),
        "status": "available",
        "checksum": value.manifest_checksum,
        "manifest": value.manifest,
    }


@router.get("/{run_id}/validation-report", response_model=dict[str, object])
def get_validation_report(run_id: UUID, session: Session = Depends(get_db)) -> dict[str, object]:
    _find_run(session, run_id)
    value = session.scalar(
        select(BacktestValidationReport).where(BacktestValidationReport.backtest_run_id == run_id)
    )
    if value is None:
        return {
            "backtest_run_id": str(run_id),
            "overall_status": "not_evaluated",
            "is_validated": False,
            "rules": [],
        }
    return {
        "backtest_run_id": str(run_id),
        "overall_status": value.overall_status,
        "is_validated": value.is_validated,
        "rules": value.rules,
        "generated_at": value.generated_at,
    }
