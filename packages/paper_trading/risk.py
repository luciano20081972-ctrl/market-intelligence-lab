from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.database.models import (
    Asset,
    PaperFill,
    PaperPortfolio,
    PaperPosition,
    PortfolioSnapshot,
    PriceBar,
    RiskRule,
)

DEFAULT_RISK_RULES: dict[str, Decimal] = {
    "maximum_position_percentage": Decimal("0.40"),
    "maximum_total_exposure": Decimal("1.00"),
    "maximum_daily_simulated_loss": Decimal("0.05"),
    "maximum_portfolio_drawdown": Decimal("0.25"),
    "maximum_daily_trade_count": Decimal("20"),
    "maximum_sector_exposure": Decimal("0.50"),
    "minimum_cash_reserve": Decimal("0.02"),
    "maximum_order_value": Decimal("50000"),
    "stale_price_days": Decimal("3650"),
}


def create_default_risk_rules(portfolio_id: object) -> list[RiskRule]:
    return [
        RiskRule(
            portfolio_id=portfolio_id,
            rule_type=rule_type,
            limit_value=value,
            configuration={},
            is_enabled=True,
        )
        for rule_type, value in DEFAULT_RISK_RULES.items()
    ]


def portfolio_marks(
    session: Session, portfolio: PaperPortfolio
) -> tuple[Decimal, Decimal, dict[str, tuple[PaperPosition, PriceBar]]]:
    marked: dict[str, tuple[PaperPosition, PriceBar]] = {}
    market_value = Decimal("0")
    unrealized = Decimal("0")
    positions = session.scalars(
        select(PaperPosition).where(
            PaperPosition.portfolio_id == portfolio.id, PaperPosition.quantity > 0
        )
    ).all()
    for position in positions:
        bar = session.scalar(
            select(PriceBar)
            .where(PriceBar.asset_id == position.asset_id)
            .order_by(PriceBar.event_time.desc())
            .limit(1)
        )
        if bar is None:
            continue
        marked[position.asset.symbol] = (position, bar)
        value = position.quantity * bar.close
        market_value += value
        unrealized += (bar.close - position.average_cost) * position.quantity
    return portfolio.cash_balance + market_value, unrealized, marked


def evaluate_risk(
    session: Session,
    *,
    portfolio: PaperPortfolio,
    asset: Asset,
    bar: PriceBar,
    side: str,
    quantity: Decimal,
    estimated_price: Decimal,
    estimated_fees: Decimal,
) -> list[str]:
    rules = {
        rule.rule_type: rule.limit_value
        for rule in session.scalars(
            select(RiskRule).where(
                RiskRule.portfolio_id == portfolio.id, RiskRule.is_enabled.is_(True)
            )
        ).all()
    }
    reasons: list[str] = []
    equity, _, marked = portfolio_marks(session, portfolio)
    order_value = quantity * estimated_price
    current_position = session.scalar(
        select(PaperPosition).where(
            PaperPosition.portfolio_id == portfolio.id, PaperPosition.asset_id == asset.id
        )
    )
    current_quantity = current_position.quantity if current_position else Decimal("0")
    if side == "sell" and quantity > current_quantity:
        reasons.append(
            f"Sell quantity {quantity} exceeds owned quantity {current_quantity}; "
            "short selling is disabled."
        )
    maximum_order = rules.get("maximum_order_value")
    if maximum_order is not None and order_value > maximum_order:
        reasons.append(
            f"Order value {order_value:.2f} exceeds maximum order value {maximum_order:.2f}."
        )
    if side == "buy":
        remaining_cash = portfolio.cash_balance - order_value - estimated_fees
        reserve_pct = rules.get("minimum_cash_reserve", Decimal("0"))
        reserve = equity * reserve_pct
        if remaining_cash < reserve:
            reasons.append(
                f"Order would leave cash {remaining_cash:.2f}, below minimum reserve {reserve:.2f}."
            )
        projected_asset_value = (current_quantity + quantity) * estimated_price
        maximum_position = rules.get("maximum_position_percentage")
        if (
            maximum_position is not None
            and equity
            and projected_asset_value / equity > maximum_position
        ):
            reasons.append(
                f"Projected position exposure {(projected_asset_value / equity):.2%} "
                f"exceeds limit {maximum_position:.2%}."
            )
        current_exposure = sum(position.quantity * mark.close for position, mark in marked.values())
        projected_exposure = current_exposure + order_value
        maximum_total = rules.get("maximum_total_exposure")
        if maximum_total is not None and equity and projected_exposure / equity > maximum_total:
            reasons.append(
                f"Projected total exposure {(projected_exposure / equity):.2%} "
                f"exceeds limit {maximum_total:.2%}."
            )
        sector_value = (
            sum(
                position.quantity * mark.close
                for position, mark in marked.values()
                if position.asset.sector == asset.sector
            )
            + order_value
        )
        maximum_sector = rules.get("maximum_sector_exposure")
        if maximum_sector is not None and equity and sector_value / equity > maximum_sector:
            reasons.append(
                f"Projected {asset.sector or 'unclassified'} sector exposure "
                f"{(sector_value / equity):.2%} exceeds limit {maximum_sector:.2%}."
            )
    stale_days = rules.get("stale_price_days")
    if stale_days is not None:
        age_days = Decimal(str(max((date.today() - bar.retrieval_time.date()).days, 0)))
        if age_days > stale_days:
            reasons.append(
                f"Stored price is {age_days} days old, exceeding stale-price limit "
                f"{stale_days} days."
            )
    trade_limit = rules.get("maximum_daily_trade_count")
    if trade_limit is not None:
        fills_today = (
            session.scalar(
                select(func.count(PaperFill.id)).where(
                    PaperFill.portfolio_id == portfolio.id,
                    func.date(PaperFill.filled_at) == bar.event_time.date().isoformat(),
                )
            )
            or 0
        )
        if fills_today >= int(trade_limit):
            reasons.append(f"Daily simulated trade limit of {int(trade_limit)} has been reached.")
    snapshots = session.scalars(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.portfolio_id == portfolio.id)
        .order_by(PortfolioSnapshot.event_time)
    ).all()
    if snapshots:
        peak = max(snapshot.equity for snapshot in snapshots)
        drawdown_limit = rules.get("maximum_portfolio_drawdown")
        if drawdown_limit is not None and peak and (peak - equity) / peak >= drawdown_limit:
            reasons.append(
                f"Portfolio drawdown {((peak - equity) / peak):.2%} reached limit "
                f"{drawdown_limit:.2%}."
            )
        daily_loss_limit = rules.get("maximum_daily_simulated_loss")
        same_day = [
            snapshot
            for snapshot in snapshots
            if snapshot.event_time.date() == bar.event_time.date()
        ]
        if daily_loss_limit is not None and same_day and same_day[0].equity:
            daily_loss = (same_day[0].equity - equity) / same_day[0].equity
            if daily_loss >= daily_loss_limit:
                reasons.append(
                    f"Daily simulated loss {daily_loss:.2%} reached limit {daily_loss_limit:.2%}."
                )
    return reasons
