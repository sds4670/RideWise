"""High-level orchestration over the individual rule functions.

These compose charges/refunds/late_fees with DB rows into a single breakdown a
tool can return to the agent, including the policy document(s) relied on so the
answer can cite its sources. Not yet implemented.
"""
from __future__ import annotations


def quote_refund(booking_row: dict, payments: list[dict]) -> dict:
    """Full refund quote for a booking: version, lead time, percent, amounts, sources."""
    raise NotImplementedError


def quote_late_fee(booking_row: dict, vehicle_row: dict, customer_row: dict) -> dict:
    """Late fee quote for a completed booking, with grace handling and sources."""
    raise NotImplementedError


def final_charges(booking_id: str) -> dict:
    """Combine rental, late fee, battery fee and charged damage for a booking."""
    raise NotImplementedError
