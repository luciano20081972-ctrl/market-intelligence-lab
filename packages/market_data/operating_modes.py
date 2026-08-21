from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.core.time import utc_now
from packages.database.models import ExchangeCalendar, MarketOperatingState, TradingSession

MODES = ("ECONOMY", "PRE_MARKET", "MARKET", "POST_MARKET")


def determine_operating_mode(
    session: Session, *, calendar_code: str = "XNYS", at: datetime | None = None
) -> MarketOperatingState:
    """Resolve state from persisted exchange sessions, including DST and early closes."""
    now = at or utc_now()
    if now.tzinfo is None:
        raise ValueError("Operating-mode timestamp must include a timezone")
    calendar = session.scalar(
        select(ExchangeCalendar).where(ExchangeCalendar.code == calendar_code)
    )
    if calendar is None:
        raise ValueError(f"Exchange calendar '{calendar_code}' is not configured")
    relevant = session.scalars(
        select(TradingSession)
        .where(
            TradingSession.calendar_id == calendar.id,
            TradingSession.close_time >= now - timedelta(hours=2),
        )
        .order_by(TradingSession.open_time)
        .limit(2)
    ).all()
    current = next(
        (
            item
            for item in relevant
            if item.open_time - timedelta(hours=2) <= now <= item.close_time + timedelta(hours=2)
        ),
        None,
    )
    if current is None:
        mode, reason = "ECONOMY", "Outside the maintained session transition window"
        next_transition = relevant[0].open_time - timedelta(hours=2) if relevant else None
        market_open = market_close = None
        session_date = None
    elif now < current.open_time:
        mode, reason = "PRE_MARKET", "Within two hours of maintained exchange open"
        next_transition = current.open_time
        market_open, market_close, session_date = (
            current.open_time,
            current.close_time,
            current.session_date,
        )
    elif now <= current.close_time:
        mode, reason = "MARKET", "Maintained exchange core session is open"
        next_transition = current.close_time
        market_open, market_close, session_date = (
            current.open_time,
            current.close_time,
            current.session_date,
        )
    else:
        mode, reason = "POST_MARKET", "Within two hours after maintained exchange close"
        next_transition = current.close_time + timedelta(hours=2)
        market_open, market_close, session_date = (
            current.open_time,
            current.close_time,
            current.session_date,
        )
    state = MarketOperatingState(
        calendar_code=calendar_code,
        mode=mode,
        effective_at=now,
        session_date=session_date,
        market_open=market_open,
        market_close=market_close,
        next_transition_at=next_transition,
        reason=reason,
        scheduler_state={
            "ingestion_heavy_limit": 1,
            "lightweight_intelligence_limit": 1,
            "defer_cpu_heavy": mode == "MARKET",
            "minimum_headroom_mb": 1024,
        },
    )
    session.add(state)
    session.flush()
    return state
