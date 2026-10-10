"""Late return fee. Pure functions.

Each late hour or part-hour is 1.5 x hourly rate + GST (RW-POL-04 cl.1.2).
GOLD tier has a 30-minute grace; once exceeded the full lateness is charged
(RW-POL-04 Annexure A). Not yet implemented.
"""
from __future__ import annotations

from src.rules.loader import load_policy  # noqa: F401


def late_minutes(scheduled_end_utc: str, actual_return_utc: str) -> int:
    """Minutes late (scheduled_end -> actual_return), floored at 0."""
    raise NotImplementedError


def late_fee(minutes_late: int, hourly_rate: float, customer_tier: str) -> float:
    """Late fee ex-GST. Applies GOLD grace; charges ceil(minutes/60) late hours."""
    raise NotImplementedError
