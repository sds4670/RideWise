"""Tests for the DB read helpers (scoped, SUCCESS/BOOKING only)."""
import pytest

from src.config import DB_PATH
from src.db.connection import connect_for_session
from src.db.repo import rental_paid, recorded_penalties
from src.security.scope import Role, Session

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="data/ridewise.db not present")


def test_rental_paid_sums_success_booking_only():
    # B-1163 belongs to its customer; find the owner via an agent session.
    agent = connect_for_session(Session(role=Role.AGENT))
    owner = agent.execute(
        "SELECT customer_id FROM bookings WHERE booking_id='B-1163'"
    ).fetchone()["customer_id"]
    agent.close()

    conn = connect_for_session(Session(role=Role.CUSTOMER, customer_id=owner))
    amt, gst = rental_paid(conn, "B-1163")
    conn.close()
    assert amt == 540.0 and gst == 97.2   # the SUCCESS BOOKING row only


def test_rental_paid_is_scoped_to_session_customer():
    # A different customer cannot see B-1163's payments: helper returns zeros.
    conn = connect_for_session(Session(role=Role.CUSTOMER, customer_id="CUST0199"))
    amt, gst = rental_paid(conn, "B-1163")
    conn.close()
    assert (amt, gst) == (0.0, 0.0)


def test_recorded_penalties_for_b0004_battery():
    conn = connect_for_session(Session(role=Role.CUSTOMER, customer_id="CUST0002"))
    pens = recorded_penalties(conn, "B-0004")
    conn.close()
    battery = [p for p in pens if "battery" in (p["remarks"] or "").lower()]
    assert battery and battery[0]["amount"] == 150.0
