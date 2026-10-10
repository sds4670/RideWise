"""Typed, parameterised read helpers over the role-scoped views.

These run against the TEMP views (so they inherit the session's scope and
masking) using bound parameters - never string-built SQL. The agent tools and
the rules engine callers use these instead of ad-hoc queries.

Two kinds of number must never be confused (see CLAUDE.md):
  - policy_says: what the rules engine computes from policy.
  - recorded:    what the DB payment/claim rows actually show, with status.
Helpers whose name starts with ``recorded_`` read the second kind.
"""
from __future__ import annotations

import sqlite3


def _round2(x) -> float:
    return round(float(x or 0), 2)


def rental_paid(conn: sqlite3.Connection, booking_id: str) -> tuple[float, float]:
    """(amount_ex_gst, gst) actually paid for the rental.

    Sums only SUCCESS payments of type BOOKING (RW-POL-01 cl.4.4). This is the
    base that refund_quote must be applied to; callers must use this helper.
    """
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS amt, COALESCE(SUM(gst_amount), 0) AS gst "
        "FROM payments "
        "WHERE booking_id = ? AND payment_status = 'SUCCESS' AND payment_type = 'BOOKING'",
        (booking_id,),
    ).fetchone()
    return (_round2(row["amt"]), _round2(row["gst"]))


def recorded_penalties(conn: sqlite3.Connection, booking_id: str) -> list[dict]:
    """Recorded PENALTY payment rows (late fee, battery, damage), with status."""
    rows = conn.execute(
        "SELECT payment_id, amount, gst_amount, payment_status, remarks, paid_at "
        "FROM payments WHERE booking_id = ? AND payment_type = 'PENALTY' "
        "ORDER BY paid_at",
        (booking_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def recorded_refunds(conn: sqlite3.Connection, booking_id: str) -> list[dict]:
    """Recorded REFUND payment rows (negative amounts), with status."""
    rows = conn.execute(
        "SELECT payment_id, amount, gst_amount, payment_status, remarks, paid_at "
        "FROM payments WHERE booking_id = ? AND payment_type = 'REFUND' "
        "ORDER BY paid_at",
        (booking_id,),
    ).fetchall()
    return [dict(r) for r in rows]
