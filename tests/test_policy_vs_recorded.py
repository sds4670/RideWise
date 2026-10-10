"""policy_says vs recorded.

A computed policy amount is not the same as a charge that actually happened.
These tests pin the distinction against real rows, and recompute recorded late
fees from the engine.

B-0004 is the anchor case:
  - EV returned at 7% battery -> policy battery fee 150 AND a recorded battery
    penalty of 150 (they match: a charge that happened).
  - Damage report DMG0002: 1200 assessed but claim_status OPEN -> only CHARGED
    is billable (RW-POL-04 cl.3.1), so there is NO recorded damage charge
    (policy/assessment != a charge that happened).

Note: the original task framing said B-0004 had "no penalty row recorded" for
the battery fee; the data shows the battery fee WAS recorded. The genuine
"assessed but not charged" case on B-0004 is the OPEN damage report, covered here.
"""
import math
import sqlite3

import pytest

from src.config import DB_PATH
from src.db.connection import connect_for_session
from src.db.repo import recorded_penalties
from src.rules.engine import battery_fee, late_fee
from src.rules.loader import load_policy
from src.rules.time_utils import parse_db_utc
from src.security.scope import Role, Session

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="data/ridewise.db not present")


def _ro():
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def test_b0004_battery_policy_matches_recorded():
    # policy_says
    policy = battery_fee(7)
    assert policy["status"] == "applies" and policy["fee"] == 150.0
    # recorded
    conn = connect_for_session(Session(role=Role.CUSTOMER, customer_id="CUST0002"))
    pens = recorded_penalties(conn, "B-0004")
    conn.close()
    battery = [p for p in pens if "battery" in (p["remarks"] or "").lower()]
    assert battery and battery[0]["amount"] == 150.0  # charge that happened


def test_b0004_damage_assessed_but_not_charged():
    chargeable = load_policy()["damage"]["chargeable_statuses"]
    conn = _ro()
    dmg = conn.execute(
        "SELECT report_id, assessed_cost, claim_status FROM damage_reports "
        "WHERE report_id = 'DMG0002'"
    ).fetchone()
    # assessment exists...
    assert dmg["assessed_cost"] == 1200.0
    # ...but status is not billable...
    assert dmg["claim_status"] not in chargeable
    # ...and nothing was charged for it.
    charged = conn.execute(
        "SELECT COUNT(*) AS n FROM payments WHERE booking_id = 'B-0004' "
        "AND payment_type = 'PENALTY' AND remarks LIKE ?",
        (f"%{dmg['report_id']}%",),
    ).fetchone()["n"]
    conn.close()
    assert charged == 0


def test_recorded_late_fees_recompute_from_engine():
    conn = _ro()
    rows = conn.execute(
        "SELECT p.booking_id, p.amount, b.scheduled_end, b.actual_return_at, "
        "v.hourly_rate, cu.customer_tier "
        "FROM payments p "
        "JOIN bookings b ON p.booking_id = b.booking_id "
        "JOIN vehicles v ON b.vehicle_id = v.vehicle_id "
        "JOIN customers cu ON b.customer_id = cu.customer_id "
        "WHERE p.payment_type = 'PENALTY' AND p.payment_status = 'SUCCESS' "
        "AND lower(p.remarks) LIKE 'late return%' "
        "LIMIT 20"
    ).fetchall()
    conn.close()
    assert len(rows) == 20
    for r in rows:
        minutes = int(
            (parse_db_utc(r["actual_return_at"]) - parse_db_utc(r["scheduled_end"])
             ).total_seconds() / 60
        )
        computed = late_fee(minutes, r["hourly_rate"], r["customer_tier"])["fee"]
        assert computed == r["amount"], (
            f"{r['booking_id']}: engine {computed} != recorded {r['amount']}"
        )
