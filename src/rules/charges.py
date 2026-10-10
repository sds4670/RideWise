"""Rental charge, deposit, GST and EV battery fee. Pure functions.

Constants come from policy_rules.yaml via loader.load_policy(). Not yet
implemented; signatures and policy references are fixed so the maths is
traceable when filled in.
"""
from __future__ import annotations

import math  # noqa: F401  (used once implemented)

from src.rules.loader import load_policy  # noqa: F401


def rental_hours(scheduled_start: str, scheduled_end: str) -> int:
    """Whole booked hours, minimum 2 (RW-POL-01 cl.3.2)."""
    raise NotImplementedError


def rental_charge(hours: int, hourly_rate: float, daily_rate: float) -> float:
    """full_days*daily_rate + min(remaining_hours*hourly_rate, daily_rate).

    RW-POL-01 cl.4.1. GST not included here; add via add_gst().
    """
    raise NotImplementedError


def add_gst(amount: float) -> float:
    """Add 18% GST (RW-POL-01 cl.4.3). Deposits must not pass through here."""
    raise NotImplementedError


def deposit(vehicle_type: str, hours: int) -> float:
    """Security deposit by vehicle type and duration (RW-POL-01 cl.5.1). No GST."""
    raise NotImplementedError


def ev_battery_fee(return_battery_pct: int | None) -> float:
    """Flat low-battery fee if return pct < threshold (RW-POL-04 cl.2). Ex-GST."""
    raise NotImplementedError
