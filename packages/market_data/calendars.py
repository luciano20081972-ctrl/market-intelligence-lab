from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.database.models import ExchangeCalendar, TradingSession

XNYS_HOLIDAYS = {
    "2025-01-01",
    "2025-01-20",
    "2025-02-17",
    "2025-04-18",
    "2025-05-26",
    "2025-06-19",
    "2025-07-04",
    "2025-09-01",
    "2025-11-27",
    "2025-12-25",
    "2026-01-01",
    "2026-01-19",
    "2026-02-16",
    "2026-04-03",
    "2026-05-25",
    "2026-06-19",
    "2026-07-03",
    "2026-09-07",
    "2026-11-26",
    "2026-12-25",
    "2027-01-01",
    "2027-01-18",
    "2027-02-15",
    "2027-03-26",
    "2027-05-31",
    "2027-06-18",
    "2027-07-05",
    "2027-09-06",
    "2027-11-25",
    "2027-12-24",
}
XNYS_EARLY_CLOSES = {
    "2025-07-03",
    "2025-11-28",
    "2025-12-24",
    "2026-11-27",
    "2026-12-24",
    "2027-11-26",
    "2027-12-23",
}


def is_open_session(calendar: ExchangeCalendar, session_date: date) -> bool:
    return session_date.weekday() not in set(
        calendar.weekend_days
    ) and session_date.isoformat() not in set(calendar.holiday_dates)


def session_times(
    session_date: date, timezone_name: str, *, early_close: bool = False
) -> tuple[datetime, datetime]:
    timezone = ZoneInfo(timezone_name)
    local_open = datetime.combine(session_date, time(9, 30), tzinfo=timezone)
    local_close = datetime.combine(
        session_date, time(13, 0) if early_close else time(16, 0), tzinfo=timezone
    )
    return local_open.astimezone(UTC), local_close.astimezone(UTC)


def generate_sessions(
    session: Session,
    calendar: ExchangeCalendar,
    start_date: date,
    end_date: date,
    *,
    early_closes: set[str] | None = None,
) -> int:
    if start_date > end_date:
        raise ValueError("start_date must not be after end_date")
    early = early_closes or set()
    existing = set(
        session.scalars(
            select(TradingSession.session_date).where(TradingSession.calendar_id == calendar.id)
        ).all()
    )
    inserted = 0
    current = start_date
    while current <= end_date:
        current_string = current.isoformat()
        if is_open_session(calendar, current) and current_string not in existing:
            is_early = current_string in early
            open_time, close_time = session_times(current, calendar.timezone, early_close=is_early)
            session.add(
                TradingSession(
                    calendar_id=calendar.id,
                    session_date=current_string,
                    open_time=open_time,
                    close_time=close_time,
                    is_early_close=is_early,
                    status="open",
                )
            )
            inserted += 1
        current += timedelta(days=1)
    return inserted


def valid_session_dates(
    session: Session, calendar_code: str, start: datetime, end: datetime
) -> set[str]:
    return set(
        session.scalars(
            select(TradingSession.session_date)
            .join(ExchangeCalendar)
            .where(
                ExchangeCalendar.code == calendar_code,
                TradingSession.open_time >= start,
                TradingSession.close_time <= end + timedelta(days=1),
            )
        ).all()
    )
