"""Time handling. All DB timestamps are naive UTC strings; users see IST.

The DB stores timestamps as "YYYY-MM-DD HH:MM:SS" in UTC with no timezone
suffix. We parse them as UTC, and present them to users in IST (+05:30) with an
explicit label so there is never ambiguity about which zone a time is in.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

UTC = timezone.utc
IST = timezone(timedelta(hours=5, minutes=30))
_DB_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_db_utc(value: str | None) -> datetime | None:
    """Parse a DB timestamp string as an aware UTC datetime. None stays None."""
    if value is None or str(value).strip() == "":
        return None
    dt = datetime.strptime(str(value).strip(), _DB_FORMAT)
    return dt.replace(tzinfo=UTC)


def to_ist(dt: datetime | None) -> datetime | None:
    """Convert an aware datetime to IST."""
    if dt is None:
        return None
    return dt.astimezone(IST)


def format_ist(value: str | datetime | None) -> str:
    """Format a DB UTC string (or datetime) as a labelled IST string for users."""
    dt = parse_db_utc(value) if isinstance(value, str) else value
    if dt is None:
        return "not recorded"
    return to_ist(dt).strftime("%Y-%m-%d %H:%M") + " IST"


def now_utc() -> datetime:
    """Current time from the real system clock, as aware UTC."""
    return datetime.now(UTC)
