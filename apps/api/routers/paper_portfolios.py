from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db
from apps.api.schemas_sprint2 import (
    FillResponse,
    OrderPayload,
    OrderPreviewResponse,
    OrderResponse,
    PaperPortfolioCreate,
    PaperPortfolioResponse,
    PerformanceResponse,
    PositionResponse,
    RiskRuleResponse,
    RiskRuleUpdate,
)
from packages.core.time import utc_now
from packages.database.models import (
    PaperFill,
    PaperOrder,
    PaperPortfolio,
    PaperPosition,
    PortfolioSnapshot,
    PriceBar,
    RiskRule,
)
from packages.paper_trading.engine import PaperTradingEngine
from packages.paper_trading.risk import portfolio_marks
from packages.paper_trading.service import create_portfolio
from packages.provenance import record_audit_event

router = APIRouter(prefix="/paper-portfolios", tags=["paper portfolios"])


def _find_portfolio(session: Session, portfolio_id: UUID) -> PaperPortfolio:
    portfolio = session.get(PaperPortfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Paper portfolio was not found")
    return portfolio


def _find_order(session: Session, portfolio_id: UUID, order_id: UUID) -> PaperOrder:
    order = session.scalar(
        select(PaperOrder).where(PaperOrder.id == order_id, PaperOrder.portfolio_id == portfolio_id)
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Simulated order was not found")
    return order


def _position_response(position: PaperPosition, mark: PriceBar | None) -> PositionResponse:
    mark_price = mark.close if mark else None
    market_value = (
        position.quantity * mark_price if mark_price else position.quantity * position.average_cost
    )
    unrealized = (
        (mark_price - position.average_cost) * position.quantity if mark_price is not None else 0
    )
    return PositionResponse(
        id=position.id,
        symbol=position.asset.symbol,
        name=position.asset.name,
        sector=position.asset.sector,
        quantity=position.quantity,
        average_cost=position.average_cost,
        mark_price=mark_price,
        market_value=market_value,
        realized_pnl=position.realized_pnl,
        unrealized_pnl=unrealized,
    )


def _portfolio_response(session: Session, portfolio: PaperPortfolio) -> PaperPortfolioResponse:
    equity, unrealized, marked = portfolio_marks(session, portfolio)
    positions = session.scalars(
        select(PaperPosition)
        .where(PaperPosition.portfolio_id == portfolio.id, PaperPosition.quantity > 0)
        .order_by(PaperPosition.updated_at.desc())
    ).all()
    market_value = equity - portfolio.cash_balance
    exposure = market_value / equity if equity else 0
    open_orders = (
        session.scalar(
            select(func.count(PaperOrder.id)).where(
                PaperOrder.portfolio_id == portfolio.id,
                PaperOrder.status.in_(["pending", "triggered"]),
            )
        )
        or 0
    )
    return PaperPortfolioResponse(
        id=portfolio.id,
        name=portfolio.name,
        currency=portfolio.currency,
        starting_cash=portfolio.starting_cash,
        cash_balance=portfolio.cash_balance,
        portfolio_value=equity,
        realized_pnl=portfolio.realized_pnl,
        unrealized_pnl=unrealized,
        exposure=exposure,
        status=portfolio.status,
        positions=[
            _position_response(position, marked.get(position.asset.symbol, (position, None))[1])
            for position in positions
        ],
        open_order_count=open_orders,
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
    )


def _order_response(order: PaperOrder, idempotent_replay: bool = False) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        client_order_id=order.client_order_id,
        symbol=order.asset.symbol,
        side=order.side,
        order_type=order.order_type,
        quantity=order.quantity,
        limit_price=order.limit_price,
        stop_price=order.stop_price,
        status=order.status,
        is_triggered=order.is_triggered,
        rejection_reason=order.rejection_reason,
        estimated_value=order.estimated_value,
        estimated_fees=order.estimated_fees,
        submitted_at=order.submitted_at,
        cancelled_at=order.cancelled_at,
        idempotent_replay=idempotent_replay,
    )


@router.post("", response_model=PaperPortfolioResponse, status_code=status.HTTP_201_CREATED)
def create_paper_portfolio(
    payload: PaperPortfolioCreate, session: Session = Depends(get_db)
) -> PaperPortfolioResponse:
    try:
        portfolio = create_portfolio(
            session, name=payload.name, starting_cash=payload.starting_cash
        )
        record_audit_event(
            session,
            action="paper_portfolio.created",
            entity_type="paper_portfolio",
            entity_id=portfolio.id,
            details={"starting_cash": str(payload.starting_cash)},
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="A paper portfolio with that name already exists"
        ) from exc
    return _portfolio_response(session, _find_portfolio(session, portfolio.id))


@router.get("", response_model=list[PaperPortfolioResponse])
def list_paper_portfolios(
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    portfolio_status: str | None = Query(default=None, alias="status"),
) -> list[PaperPortfolioResponse]:
    filters = [PaperPortfolio.status == portfolio_status] if portfolio_status else []
    portfolios = session.scalars(
        select(PaperPortfolio)
        .where(*filters)
        .order_by(PaperPortfolio.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [_portfolio_response(session, portfolio) for portfolio in portfolios]


@router.get("/{portfolio_id}", response_model=PaperPortfolioResponse)
def get_paper_portfolio(
    portfolio_id: UUID, session: Session = Depends(get_db)
) -> PaperPortfolioResponse:
    return _portfolio_response(session, _find_portfolio(session, portfolio_id))


@router.post("/{portfolio_id}/orders/preview", response_model=OrderPreviewResponse)
def preview_order(
    portfolio_id: UUID, payload: OrderPayload, session: Session = Depends(get_db)
) -> OrderPreviewResponse:
    portfolio = _find_portfolio(session, portfolio_id)
    try:
        preview = PaperTradingEngine().preview(session, portfolio, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return OrderPreviewResponse(**preview.__dict__)


@router.post(
    "/{portfolio_id}/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED
)
def submit_order(
    portfolio_id: UUID, payload: OrderPayload, session: Session = Depends(get_db)
) -> OrderResponse:
    portfolio = _find_portfolio(session, portfolio_id)
    try:
        result = PaperTradingEngine().submit(session, portfolio, payload)
        order = _find_order(session, portfolio.id, result.order_id)
        if not result.idempotent_replay:
            record_audit_event(
                session,
                action="paper_order.submitted",
                entity_type="paper_order",
                entity_id=order.id,
                details={"status": order.status, "symbol": order.asset.symbol},
            )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _order_response(_find_order(session, portfolio.id, order.id), result.idempotent_replay)


@router.delete("/{portfolio_id}/orders/{order_id}", response_model=OrderResponse)
def cancel_order(
    portfolio_id: UUID, order_id: UUID, session: Session = Depends(get_db)
) -> OrderResponse:
    _find_portfolio(session, portfolio_id)
    order = _find_order(session, portfolio_id, order_id)
    try:
        PaperTradingEngine().cancel(order)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record_audit_event(
        session,
        action="paper_order.cancelled",
        entity_type="paper_order",
        entity_id=order.id,
        details={},
    )
    session.commit()
    return _order_response(order)


@router.get("/{portfolio_id}/orders", response_model=list[OrderResponse])
def list_orders(
    portfolio_id: UUID,
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    order_status: str | None = Query(default=None, alias="status"),
    sort_direction: Literal["asc", "desc"] = "desc",
) -> list[OrderResponse]:
    _find_portfolio(session, portfolio_id)
    filters = [PaperOrder.portfolio_id == portfolio_id]
    if order_status:
        filters.append(PaperOrder.status == order_status)
    ordering = (
        asc(PaperOrder.submitted_at) if sort_direction == "asc" else desc(PaperOrder.submitted_at)
    )
    orders = session.scalars(
        select(PaperOrder)
        .where(*filters)
        .order_by(ordering)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [_order_response(order) for order in orders]


@router.get("/{portfolio_id}/fills", response_model=list[FillResponse])
def list_fills(
    portfolio_id: UUID,
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
) -> list[FillResponse]:
    _find_portfolio(session, portfolio_id)
    fills = session.scalars(
        select(PaperFill)
        .where(PaperFill.portfolio_id == portfolio_id)
        .order_by(PaperFill.filled_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [
        FillResponse(
            id=fill.id,
            order_id=fill.order_id,
            symbol=fill.asset.symbol,
            side=fill.side,
            quantity=fill.quantity,
            price=fill.price,
            gross_value=fill.gross_value,
            fees=fill.fees,
            filled_at=fill.filled_at,
            source_price_bar_id=fill.source_price_bar_id,
        )
        for fill in fills
    ]


@router.get("/{portfolio_id}/positions", response_model=list[PositionResponse])
def list_positions(
    portfolio_id: UUID, session: Session = Depends(get_db)
) -> list[PositionResponse]:
    portfolio = _find_portfolio(session, portfolio_id)
    _, _, marked = portfolio_marks(session, portfolio)
    positions = session.scalars(
        select(PaperPosition).where(
            PaperPosition.portfolio_id == portfolio_id, PaperPosition.quantity > 0
        )
    ).all()
    return [
        _position_response(position, marked.get(position.asset.symbol, (position, None))[1])
        for position in positions
    ]


@router.get("/{portfolio_id}/performance", response_model=PerformanceResponse)
def get_performance(portfolio_id: UUID, session: Session = Depends(get_db)) -> PerformanceResponse:
    portfolio = _find_portfolio(session, portfolio_id)
    current_value, unrealized, _ = portfolio_marks(session, portfolio)
    snapshots = session.scalars(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.portfolio_id == portfolio_id)
        .order_by(PortfolioSnapshot.event_time)
    ).all()
    return PerformanceResponse(
        portfolio_id=portfolio.id,
        starting_cash=portfolio.starting_cash,
        current_value=current_value,
        total_return=current_value / portfolio.starting_cash - 1,
        realized_pnl=portfolio.realized_pnl,
        unrealized_pnl=unrealized,
        points=[
            {
                "event_time": snapshot.event_time,
                "equity": snapshot.equity,
                "cash": snapshot.cash,
                "realized_pnl": snapshot.realized_pnl,
                "unrealized_pnl": snapshot.unrealized_pnl,
                "exposure": snapshot.exposure,
            }
            for snapshot in snapshots
        ],
    )


@router.post("/{portfolio_id}/pause", response_model=PaperPortfolioResponse)
def pause_portfolio(
    portfolio_id: UUID, session: Session = Depends(get_db)
) -> PaperPortfolioResponse:
    portfolio = _find_portfolio(session, portfolio_id)
    portfolio.status = "paused"
    portfolio.updated_at = utc_now()
    session.commit()
    return _portfolio_response(session, portfolio)


@router.post("/{portfolio_id}/resume", response_model=PaperPortfolioResponse)
def resume_portfolio(
    portfolio_id: UUID, session: Session = Depends(get_db)
) -> PaperPortfolioResponse:
    portfolio = _find_portfolio(session, portfolio_id)
    portfolio.status = "active"
    portfolio.updated_at = utc_now()
    session.commit()
    return _portfolio_response(session, portfolio)


@router.get("/{portfolio_id}/risk-rules", response_model=list[RiskRuleResponse])
def list_risk_rules(
    portfolio_id: UUID, session: Session = Depends(get_db)
) -> list[RiskRuleResponse]:
    _find_portfolio(session, portfolio_id)
    rules = session.scalars(
        select(RiskRule).where(RiskRule.portfolio_id == portfolio_id).order_by(RiskRule.rule_type)
    ).all()
    return [
        RiskRuleResponse(
            id=rule.id,
            rule_type=rule.rule_type,
            limit_value=rule.limit_value,
            is_enabled=rule.is_enabled,
            configuration=rule.configuration,
        )
        for rule in rules
    ]


@router.patch("/{portfolio_id}/risk-rules/{rule_id}", response_model=RiskRuleResponse)
def update_risk_rule(
    portfolio_id: UUID,
    rule_id: UUID,
    payload: RiskRuleUpdate,
    session: Session = Depends(get_db),
) -> RiskRuleResponse:
    _find_portfolio(session, portfolio_id)
    rule = session.scalar(
        select(RiskRule).where(RiskRule.id == rule_id, RiskRule.portfolio_id == portfolio_id)
    )
    if rule is None:
        raise HTTPException(status_code=404, detail="Risk rule was not found")
    rule.limit_value = payload.limit_value
    rule.is_enabled = payload.is_enabled
    rule.updated_at = utc_now()
    session.commit()
    return RiskRuleResponse(
        id=rule.id,
        rule_type=rule.rule_type,
        limit_value=rule.limit_value,
        is_enabled=rule.is_enabled,
        configuration=rule.configuration,
    )
