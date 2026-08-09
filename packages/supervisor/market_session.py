from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum

import exchange_calendars  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]


class MarketSessionState(StrEnum):
    CLOSED = "CLOSED"
    PREMARKET = "PREMARKET"
    REGULAR = "REGULAR"
    POSTMARKET = "POSTMARKET"


def market_session_state(
    at: datetime | None = None, calendar_name: str = "XNYS"
) -> MarketSessionState:
    moment = (at or datetime.now(UTC)).astimezone(UTC)
    minute = pd.Timestamp(moment).floor("min")
    calendar = exchange_calendars.get_calendar(calendar_name)
    if calendar.is_open_on_minute(minute, ignore_breaks=True):
        return MarketSessionState.REGULAR
    try:
        session = calendar.minute_to_session(minute, direction="next")
        opens = calendar.session_open(session).to_pydatetime().astimezone(UTC)
        if opens - timedelta(hours=5, minutes=30) <= moment < opens:
            return MarketSessionState.PREMARKET
    except (ValueError, KeyError):
        pass
    try:
        previous = calendar.minute_to_session(minute, direction="previous")
        closes = calendar.session_close(previous).to_pydatetime().astimezone(UTC)
        if closes < moment <= closes + timedelta(hours=4):
            return MarketSessionState.POSTMARKET
    except (ValueError, KeyError):
        pass
    return MarketSessionState.CLOSED
