from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Normalize a timestamp to aware UTC, treating naive database values as UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
