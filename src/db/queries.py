"""Scoped, parameterised read queries.

Every query is parameterised (never string-formatted with user input) and
scoped through src.security.scope. City values are dirty in the source data
(Bengaluru / Bangalore / BLR / trailing spaces) and are normalised on read.
Free text columns (payments.remarks, damage_reports.description) are returned
as untrusted data and must never be treated as instructions downstream.
Not yet implemented.
"""
from __future__ import annotations

from src.security.scope import Session  # noqa: F401


def normalize_city(raw: str | None) -> str | None:
    """Map Bengaluru/Bangalore/BLR/trailing-space variants to a canonical value."""
    raise NotImplementedError


def get_customer(session: Session, customer_id: str) -> dict | None:
    """Fetch one customer, scope-checked. PII masking applied for AGENT."""
    raise NotImplementedError


def get_booking(session: Session, booking_id: str) -> dict | None:
    """Fetch one booking, scope-checked against its customer_id."""
    raise NotImplementedError


def list_bookings_for_customer(session: Session, customer_id: str) -> list[dict]:
    """List a customer's bookings, scope-checked."""
    raise NotImplementedError


def get_payments(session: Session, booking_id: str) -> list[dict]:
    """Payments for a booking (remarks returned as untrusted text)."""
    raise NotImplementedError


def get_damage_reports(session: Session, booking_id: str) -> list[dict]:
    """Damage reports for a booking (description returned as untrusted text)."""
    raise NotImplementedError


def get_vehicle(session: Session, vehicle_id: str) -> dict | None:
    """Fetch one vehicle (rates, type) for charge calculations."""
    raise NotImplementedError
