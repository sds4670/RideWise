"""Rules engine tests.

Reproduces every worked example printed in the policy PDFs, plus the two
boundary bookings B-1163 (v1) and B-1165 (v2) using real DB rows.
"""
import sqlite3

import pytest

from src.config import DB_PATH
from src.rules.engine import (
    battery_fee,
    deposit_due,
    gst,
    late_fee,
    refund_quote,
    refund_version,
    rental_charge,
)


# --- Rental charge (RW-POL-01 cl.4.2 worked examples, rates 80 / 700) ----

@pytest.mark.parametrize(
    "hours,expected",
    [(4, 320), (10, 700), (24, 700), (27, 940)],
)
def test_rental_charge_examples(hours, expected):
    assert rental_charge(hours, hourly_rate=80, daily_rate=700)["charge"] == expected


# --- Late fee (RW-POL-04 cl.1.4 worked examples, hourly rate 100) --------

@pytest.mark.parametrize(
    "minutes,expected",
    [(5, 150), (59, 150), (61, 300), (180, 450), (195, 600)],
)
def test_late_fee_examples_no_grace(minutes, expected):
    assert late_fee(minutes, hourly_rate=100, customer_tier="STANDARD")["fee"] == expected


def test_gold_grace_within_30_min_is_free():
    assert late_fee(30, hourly_rate=100, customer_tier="GOLD")["fee"] == 0.0


def test_gold_grace_exceeded_charges_full_lateness():
    # 31 min late -> grace exceeded -> 1 late hour -> 150.
    assert late_fee(31, hourly_rate=100, customer_tier="GOLD")["fee"] == 150


# --- EV battery fee (RW-POL-04 cl.2) -------------------------------------

@pytest.mark.parametrize("pct,expected", [(9, 150), (10, 0), (50, 0), (None, 0)])
def test_battery_fee(pct, expected):
    assert battery_fee(pct)["fee"] == expected


# --- Deposit (RW-POL-01 cl.5.1) ------------------------------------------

@pytest.mark.parametrize(
    "vtype,hours,expected",
    [
        ("BIKE", 2, 1000),
        ("EV_BIKE", 2, 1000),
        ("SCOOTER", 12, 0),
        ("SCOOTER", 24, 500),
        ("EV_SCOOTER", 23, 0),
        ("EV_SCOOTER", 24, 500),
    ],
)
def test_deposit_due(vtype, hours, expected):
    assert deposit_due(vtype, hours)["deposit"] == expected


# --- GST helper ----------------------------------------------------------

def test_gst_on_500():
    assert gst(500)["gst"] == 90.0


# --- Refund: PDF v1 worked example (500 paid, 12h before -> 50%) ---------

def test_refund_v1_pdf_example():
    # Booked 2026-05-10 18:00 IST (= 12:30 UTC) -> v1.
    # Scheduled pickup 2026-05-20 09:00 IST (= 03:30 UTC).
    # Cancelled 2026-05-19 21:00 IST (= 15:30 UTC) -> 12h before pickup.
    r = refund_quote(
        booked_at_utc="2026-05-10 12:30:00",
        cancelled_at_utc="2026-05-19 15:30:00",
        scheduled_start_utc="2026-05-20 03:30:00",
        rental_paid_ex_gst=500,
        gst_paid=90,
        booking_status="CNL_U",
    )
    assert r["version"] == "v1"
    assert r["percent"] == 50
    assert r["rental_refund"] == 250.0
    assert r["gst_refund"] == 45.0
    assert r["total_refund"] == 295.0


# --- Refund version boundary around the IST cutoff -----------------------

def test_refund_version_cutoff_boundary():
    # 2026-06-30 18:29:59 UTC = 2026-06-30 23:59:59 IST -> v1 (before cutoff).
    assert refund_version("2026-06-30 18:29:59") == "v1"
    # 2026-06-30 18:30:00 UTC = 2026-07-01 00:00:00 IST -> v2 (on cutoff).
    assert refund_version("2026-06-30 18:30:00") == "v2"


# --- Boundary bookings from the real DB ----------------------------------

def _booking_refund_inputs(bid):
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    b = conn.execute("SELECT * FROM bookings WHERE booking_id=?", (bid,)).fetchone()
    pays = conn.execute(
        "SELECT amount, gst_amount FROM payments "
        "WHERE booking_id=? AND payment_type='BOOKING' AND payment_status='SUCCESS'",
        (bid,),
    ).fetchall()
    conn.close()
    rental_paid = sum(p["amount"] for p in pays)
    gst_paid = sum(p["gst_amount"] for p in pays)
    return b, rental_paid, gst_paid


@pytest.mark.skipif(not DB_PATH.exists(), reason="data/ridewise.db not present")
def test_boundary_B1163_is_v1_50pct():
    b, rental_paid, gst_paid = _booking_refund_inputs("B-1163")
    r = refund_quote(
        b["booked_at"], b["cancelled_at"], b["scheduled_start"],
        rental_paid, gst_paid, b["booking_status"],
    )
    assert r["version"] == "v1"
    assert r["percent"] == 50
    assert r["rental_refund"] == 270.0   # matches DB REFUND row -270.0
    assert r["gst_refund"] == 48.6       # matches DB REFUND row -48.6


@pytest.mark.skipif(not DB_PATH.exists(), reason="data/ridewise.db not present")
def test_boundary_B1165_is_v2_75pct():
    b, rental_paid, gst_paid = _booking_refund_inputs("B-1165")
    r = refund_quote(
        b["booked_at"], b["cancelled_at"], b["scheduled_start"],
        rental_paid, gst_paid, b["booking_status"],
    )
    assert r["version"] == "v2"
    assert r["percent"] == 75
    assert r["rental_refund"] == 240.0   # matches DB REFUND row -240.0
    assert r["gst_refund"] == 43.2       # matches DB REFUND row -43.2
