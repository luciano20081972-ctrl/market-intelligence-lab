from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from packages.database.models import PaperPortfolio, PortfolioSnapshot
from packages.paper_trading.risk import create_default_risk_rules


def create_portfolio(session: Session, *, name: str, starting_cash: Decimal) -> PaperPortfolio:
    portfolio = PaperPortfolio(
        name=name,
        starting_cash=starting_cash,
        cash_balance=starting_cash,
        realized_pnl=Decimal("0"),
        status="active",
    )
    session.add(portfolio)
    session.flush()
    session.add_all(create_default_risk_rules(portfolio.id))
    session.add(
        PortfolioSnapshot(
            portfolio_id=portfolio.id,
            event_time=portfolio.created_at,
            equity=starting_cash,
            cash=starting_cash,
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            exposure=Decimal("0"),
            positions={},
        )
    )
    session.flush()
    return portfolio
