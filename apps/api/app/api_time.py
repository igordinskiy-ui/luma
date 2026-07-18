"""UTC conversion helpers for the public API contract.

The database intentionally stores naive UTC values for compatibility with the
existing SQLite/PostgreSQL schema. Values must regain their UTC meaning before
they cross the API boundary; otherwise browsers interpret them as local time.
"""
from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the database's naive-UTC representation without deprecated APIs."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_epoch() -> float:
    """Return a timezone-independent Unix timestamp for runtime heartbeats."""
    return datetime.now(timezone.utc).timestamp()


def to_utc_naive(value: datetime) -> datetime:
    """Convert an aware instant to the database's naive-UTC representation."""
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def utc_iso(value: datetime | None) -> str | None:
    """Serialize a database/API datetime as an unambiguous RFC 3339 UTC value."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")
