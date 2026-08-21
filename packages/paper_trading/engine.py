from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.core.time import utc_now
from packages.database.models import (
    Asset,
    PaperFill,
    PaperOrder,
    PaperPortfolio,
    PaperPosition,
    PortfolioSnapshot,
    PriceBar,
)
from packages.paper_trading.risk import evaluate_risk, portfolio_marks
from packages.paper_trading.types import (
    ExecutionAssumptions,
    OrderPreview,
    OrderRequest,
    OrderResult,
)

MONEY = Decimal("0.000001")
PRICE = Decimal("0.00000001")


class PaperTradingEngine:
    def __init__(self, assumptions: ExecutionAssumptions | None = None) -> None:
        self.assumptions = assumptions or ExecutionAssumptions()

    def preview(
        self, session: Session, portfolio: PaperPortfolio, request: OrderRequest
    ) -> OrderPreview:
        asset = session.scalar(select(Asset).where(Asset.symbol == request.symbol))
        if asset is None:
            raise ValueError(f"Asset '{request.symbol}' was not found")
        bar = session.scalar(
            select(PriceBar)
            .where(PriceBar.asset_id == asset.id)
            .order_by(PriceBar.event_time.desc())
            .limit(1)
        )
        if bar is None:
            raise ValueError("PRICE DATA UNAVAILABLE OR STALE")
        base_price, outcome, triggered = self._eligible_price(request, bar, False)
        price = (
            self._apply_friction(base_price, request.side, request.limit_price)
            if base_price
            else None
        )
        value = (price * request.quantity).quantize(MONEY) if price else None
        reasons: list[str] = []
        if portfolio.status != "active":
            reasons.append("Portfolio is paused; new simulated orders are disabled.")
        risk_price = price or request.limit_price or request.stop_price or bar.close
        reasons.extend(
            evaluate_risk(
                session,
                portfolio=portfolio,
                asset=asset,
                bar=bar,
                side=request.side,
                quantity=request.quantity,
                estimated_price=risk_price,
                estimated_fees=self.assumptions.commission,
            )
        )
        if reasons:
            outcome = "rejected"
        return OrderPreview(
            outcome=outcome,
            estimated_price=price,
            estimated_value=value,
            estimated_fees=self.assumptions.commission,
            rejection_reasons=reasons,
            source_price_bar_id=bar.id,
            assumptions={
                "commission": str(self.assumptions.commission),
                "spread_bps": str(self.assumptions.spread_bps),
                "slippage_bps": str(self.assumptions.slippage_bps),
                "gap_rule": (
                    "marketable gaps use bar open; intrabar touches use threshold; "
                    "limit prices are never violated"
                ),
                "classification": "hypothetical simulated order",
            },
            is_triggered=triggered,
        )

    def submit(
        self, session: Session, portfolio: PaperPortfolio, request: OrderRequest
    ) -> OrderResult:
        existing = session.scalar(
            select(PaperOrder).where(
                PaperOrder.portfolio_id == portfolio.id,
                PaperOrder.client_order_id == request.client_order_id,
            )
        )
        if existing is not None:
            return OrderResult(existing.id, existing.status, existing.rejection_reason, True)
        asset = session.scalar(select(Asset).where(Asset.symbol == request.symbol))
        if asset is None:
            raise ValueError(f"Asset '{request.symbol}' was not found")
        preview = self.preview(session, portfolio, request)
        status = {
            "would_fill": "pending",
            "pending": "pending",
            "triggered": "triggered",
            "rejected": "rejected",
        }[preview.outcome]
        order = PaperOrder(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            client_order_id=request.client_order_id,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            limit_price=request.limit_price,
            stop_price=request.stop_price,
            status=status,
            is_triggered=preview.is_triggered,
            rejection_reason=" ".join(preview.rejection_reasons) or None,
            estimated_value=preview.estimated_value,
            estimated_fees=preview.estimated_fees,
            assumptions=preview.assumptions,
            source_price_bar_id=preview.source_price_bar_id,
        )
        session.add(order)
        session.flush()
        if preview.outcome == "would_fill" and preview.estimated_price is not None:
            bar = session.get(PriceBar, preview.source_price_bar_id)
            if bar is None:
                raise ValueError("preview source bar disappeared")
            self._fill(session, portfolio, order, bar, preview.estimated_price)
        return OrderResult(order.id, order.status, order.rejection_reason, False)

    def process_order(self, session: Session, order: PaperOrder, bar: PriceBar) -> PaperOrder:
        if order.status not in {"pending", "triggered"}:
            return order
        request = OrderRequest(
            client_order_id=order.client_order_id,
            symbol=order.asset.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            limit_price=order.limit_price,
            stop_price=order.stop_price,
        )
        base_price, outcome, triggered = self._eligible_price(request, bar, order.is_triggered)
        order.is_triggered = triggered
        order.status = "triggered" if triggered and outcome != "would_fill" else "pending"
        if base_price is not None and outcome == "would_fill":
            price = self._apply_friction(base_price, request.side, request.limit_price)
            self._fill(session, order.portfolio, order, bar, price)
        return order

    def cancel(self, order: PaperOrder) -> None:
        if order.status not in {"pending", "triggered"}:
            raise ValueError(f"Order in status '{order.status}' cannot be cancelled")
        order.status = "cancelled"
        order.cancelled_at = utc_now()

    def _fill(
        self,
        session: Session,
        portfolio: PaperPortfolio,
        order: PaperOrder,
        bar: PriceBar,
        price: Decimal,
    ) -> None:
        quantity = order.quantity
        gross = (price * quantity).quantize(MONEY)
        fee = self.assumptions.commission
        position = session.scalar(
            select(PaperPosition).where(
                PaperPosition.portfolio_id == portfolio.id,
                PaperPosition.asset_id == order.asset_id,
            )
        )
        if position is None:
            position = PaperPosition(
                portfolio_id=portfolio.id,
                asset_id=order.asset_id,
                quantity=Decimal("0"),
                average_cost=Decimal("0"),
                realized_pnl=Decimal("0"),
            )
            session.add(position)
            session.flush()
        if order.side == "buy":
            total_cost = position.quantity * position.average_cost + gross + fee
            portfolio.cash_balance -= gross + fee
            position.quantity += quantity
            position.average_cost = (total_cost / position.quantity).quantize(PRICE)
        else:
            realized = (price - position.average_cost) * quantity - fee
            portfolio.cash_balance += gross - fee
            portfolio.realized_pnl += realized
            position.realized_pnl += realized
            position.quantity -= quantity
            if position.quantity == 0:
                position.average_cost = Decimal("0")
        fill = PaperFill(
            portfolio_id=portfolio.id,
            order_id=order.id,
            asset_id=order.asset_id,
            source_price_bar_id=bar.id,
            side=order.side,
            quantity=quantity,
            price=price,
            gross_value=gross,
            fees=fee,
            filled_at=bar.event_time,
        )
        session.add(fill)
        order.status = "filled"
        order.source_price_bar_id = bar.id
        self._snapshot(session, portfolio, bar.event_time)

    def _snapshot(self, session: Session, portfolio: PaperPortfolio, event_time: object) -> None:
        session.flush()
        equity, unrealized, marked = portfolio_marks(session, portfolio)
        market_value = equity - portfolio.cash_balance
        exposure = market_value / equity if equity else Decimal("0")
        session.add(
            PortfolioSnapshot(
                portfolio_id=portfolio.id,
                event_time=event_time,
                equity=equity,
                cash=portfolio.cash_balance,
                realized_pnl=portfolio.realized_pnl,
                unrealized_pnl=unrealized,
                exposure=exposure,
                positions={
                    symbol: {
                        "quantity": str(position.quantity),
                        "average_cost": str(position.average_cost),
                        "mark": str(bar.close),
                    }
                    for symbol, (position, bar) in marked.items()
                },
            )
        )

    def _eligible_price(
        self, request: OrderRequest, bar: PriceBar, already_triggered: bool
    ) -> tuple[Decimal | None, str, bool]:
        if request.order_type == "market":
            return bar.open, "would_fill", False
        if request.order_type == "limit":
            return (*self._limit_price(request.side, bar, request.limit_price), False)
        stop_price = request.stop_price
        if stop_price is None:
            raise ValueError("stop price is required")
        stop_reached = already_triggered or (
            bar.high >= stop_price if request.side == "buy" else bar.low <= stop_price
        )
        if not stop_reached:
            return None, "pending", False
        if request.order_type == "stop":
            stop_base = (
                max(bar.open, stop_price) if request.side == "buy" else min(bar.open, stop_price)
            )
            return stop_base, "would_fill", True
        limit_base, outcome = self._limit_price(request.side, bar, request.limit_price)
        return limit_base, outcome if limit_base is not None else "triggered", True

    @staticmethod
    def _limit_price(
        side: str, bar: PriceBar, limit_price: Decimal | None
    ) -> tuple[Decimal | None, str]:
        if limit_price is None:
            raise ValueError("limit price is required")
        if side == "buy":
            if bar.open <= limit_price:
                return bar.open, "would_fill"
            if bar.low <= limit_price:
                return limit_price, "would_fill"
        else:
            if bar.open >= limit_price:
                return bar.open, "would_fill"
            if bar.high >= limit_price:
                return limit_price, "would_fill"
        return None, "pending"

    def _apply_friction(
        self, base: Decimal | None, side: str, limit_price: Decimal | None
    ) -> Decimal:
        if base is None:
            raise ValueError("base price is required")
        friction = (self.assumptions.spread_bps / 2 + self.assumptions.slippage_bps) / Decimal(
            "10000"
        )
        adjusted = base * (Decimal("1") + friction if side == "buy" else Decimal("1") - friction)
        if limit_price is not None:
            adjusted = min(adjusted, limit_price) if side == "buy" else max(adjusted, limit_price)
        return adjusted.quantize(PRICE)
