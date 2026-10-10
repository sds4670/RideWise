"""Cancellation refund calculation. Pure functions.

Policy version is chosen by booked_at in IST against the cutoff in
policy_rules.yaml (RW-POL-02 / RW-POL-03). Not yet implemented.
"""
from __future__ import annotations

from src.rules.loader import load_policy  # noqa: F401


def refund_version(booked_at_utc: str) -> str:
    """Return 'v1' or 'v2' based on booked_at converted to IST vs the cutoff."""
    raise NotImplementedError


def hours_before_pickup(cancelled_at_utc: str, scheduled_start_utc: str) -> float:
    """Hours from cancellation to scheduled pickup (RW-POL-02/03 cl.1)."""
    raise NotImplementedError


def refund_percent(version: str, hours_before: float) -> int:
    """Refund percentage for the given version and lead time (slab lookup)."""
    raise NotImplementedError


def refund_amount(rental_paid_ex_gst: float, gst_paid: float, percent: int) -> dict:
    """Refund of rental actually paid, with GST refunded in proportion.

    Returns a breakdown dict {rental_refund, gst_refund, total, percent}.
    """
    raise NotImplementedError
