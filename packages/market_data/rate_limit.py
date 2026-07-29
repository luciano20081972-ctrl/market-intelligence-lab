from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from threading import Lock


class InProcessRateLimiter:
    """Single-instance fixed-window limiter; not shared across multiple processes."""

    def __init__(self, limit: int = 10, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window = timedelta(seconds=window_seconds)
        self._events: dict[str, deque[datetime]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, *, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        with self._lock:
            events = self._events[key]
            cutoff = current - self.window
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(current)
            return True
