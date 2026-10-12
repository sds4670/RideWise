"""Tools exposed to the LLM, wired to the scoped DB layer and rules engine.

Each tool takes its scope from the session (via the role-scoped connection),
never from an LLM-supplied customer_id - any such argument is ignored. Quote
tools always return both ``policy_says`` (computed from the rules) and
``recorded`` (actual DB payment rows, with status), so a computed amount is
never presented as a charge that happened.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from src.db import repo
from src.db.validator import SQLValidationError, run_query
from src.rules import engine
from src.rules.time_utils import format_ist, now_utc
from src.security.scope import Role, Session


@dataclass
class ToolContext:
    session: Session
    conn: sqlite3.Connection


# --- internal helpers ----------------------------------------------------

def _booking(conn: sqlite3.Connection, booking_id: str):
    return conn.execute(
        "SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)
    ).fetchone()


def _vehicle(conn: sqlite3.Connection, vehicle_id: str):
    return conn.execute(
        "SELECT * FROM vehicles WHERE vehicle_id = ?", (vehicle_id,)
    ).fetchone()


def _customer_tier(conn: sqlite3.Connection, customer_id: str):
    r = conn.execute(
        "SELECT customer_tier FROM customers WHERE customer_id = ?", (customer_id,)
    ).fetchone()
    return r["customer_tier"] if r else None


def _not_found(booking_id: str) -> dict:
    return {"found": False, "message": f"No record found for booking {booking_id}."}


# --- tools ---------------------------------------------------------------

def get_booking(ctx: ToolContext, booking_id: str) -> dict:
    """Return one booking (scoped) with its vehicle and IST-labelled times."""
    b = _booking(ctx.conn, booking_id)
    if b is None:
        return _not_found(booking_id)
    v = _vehicle(ctx.conn, b["vehicle_id"])
    return {
        "found": True,
        "booking_id": b["booking_id"],
        "booking_status": b["booking_status"],
        "scheduled_start_ist": format_ist(b["scheduled_start"]),
        "scheduled_end_ist": format_ist(b["scheduled_end"]),
        "actual_return_ist": format_ist(b["actual_return_at"]),
        "cancelled_at_ist": format_ist(b["cancelled_at"]),
        "booked_at_ist": format_ist(b["booked_at"]),
        "return_battery_pct": b["return_battery_pct"],
        "vehicle": None if v is None else {
            "vehicle_id": v["vehicle_id"], "type": v["vehicle_type"],
            "model": v["model"], "hourly_rate": v["hourly_rate"],
            "daily_rate": v["daily_rate"], "hub": v["hub_name"],
        },
    }


def list_my_bookings(ctx: ToolContext) -> dict:
    """List the session customer's bookings (CUSTOMER role only)."""
    if ctx.session.role is not Role.CUSTOMER:
        return {"error": "list_my_bookings is for the customer role; "
                         "use run_sql or get_booking as an agent."}
    rows = ctx.conn.execute(
        "SELECT booking_id, booking_status, scheduled_start, scheduled_end "
        "FROM bookings ORDER BY scheduled_start DESC"
    ).fetchall()
    return {"count": len(rows), "bookings": [
        {"booking_id": r["booking_id"], "status": r["booking_status"],
         "scheduled_start_ist": format_ist(r["scheduled_start"]),
         "scheduled_end_ist": format_ist(r["scheduled_end"])}
        for r in rows
    ]}


def get_payments_summary(ctx: ToolContext, booking_id: str) -> dict:
    """Rental actually paid, plus recorded penalties and refunds (with status)."""
    if _booking(ctx.conn, booking_id) is None:
        return _not_found(booking_id)
    amt, gst = repo.rental_paid(ctx.conn, booking_id)
    return {
        "found": True,
        "rental_paid_ex_gst": amt,
        "rental_gst_paid": gst,
        "recorded_penalties": repo.recorded_penalties(ctx.conn, booking_id),
        "recorded_refunds": repo.recorded_refunds(ctx.conn, booking_id),
    }


def get_damage(ctx: ToolContext, booking_id: str) -> dict:
    """Damage reports for a booking, flagging which are actually billable."""
    if _booking(ctx.conn, booking_id) is None:
        return _not_found(booking_id)
    chargeable = engine.load_policy()["damage"]["chargeable_statuses"]
    rows = ctx.conn.execute(
        "SELECT report_id, damage_category, severity, description, assessed_cost, "
        "claim_status FROM damage_reports WHERE booking_id = ?", (booking_id,)
    ).fetchall()
    return {"found": True, "reports": [
        {"report_id": r["report_id"], "category": r["damage_category"],
         "severity": r["severity"], "description": r["description"],
         "assessed_cost": r["assessed_cost"], "claim_status": r["claim_status"],
         "billable": r["claim_status"] in chargeable}
        for r in rows
    ]}


def quote_rental(ctx: ToolContext, booking_id: str) -> dict:
    """Rental charge + GST + deposit for a booking (policy_says)."""
    b = _booking(ctx.conn, booking_id)
    if b is None:
        return _not_found(booking_id)
    v = _vehicle(ctx.conn, b["vehicle_id"])
    dur = engine.booked_hours(b["scheduled_start"], b["scheduled_end"])
    rental = engine.rental_charge(dur["hours"], v["hourly_rate"], v["daily_rate"])
    g = engine.gst(rental["charge"])
    dep = engine.deposit_due(v["vehicle_type"], dur["hours"])
    steps = (["Booked duration: " + ("whole" if dur["whole"] else
             f"rounded up from {dur['raw_hours']}h") + f" = {dur['hours']}h."]
             + rental["steps"] + g["steps"] + dep["steps"])
    return {"found": True, "policy_says": {
        "hours": dur["hours"], "rental_ex_gst": rental["charge"],
        "gst": g["gst"], "rental_incl_gst": g["total"], "deposit": dep["deposit"],
    }, "steps": steps,
        "sources": rental["sources"] + g["sources"] + dep["sources"]}


def quote_refund(ctx: ToolContext, booking_id: str) -> dict:
    """Refund: policy_says (computed) vs recorded refund rows."""
    b = _booking(ctx.conn, booking_id)
    if b is None:
        return _not_found(booking_id)
    amt, gst = repo.rental_paid(ctx.conn, booking_id)
    cancelled_at = b["cancelled_at"]
    projected = cancelled_at is None
    cancel_ts = cancelled_at or now_utc().strftime("%Y-%m-%d %H:%M:%S")
    policy = engine.refund_quote(
        b["booked_at"], cancel_ts, b["scheduled_start"], amt, gst, b["booking_status"]
    )
    if projected:
        policy["steps"].insert(0, "No cancellation on record; projecting as if "
                                  "cancelled now (current time).")
    # Attach the retrieved refund clause text (version-aware) for sources.
    from src.policy.retriever import search
    pol = search("refund on cancellation before pickup", booked_at=b["booked_at"])
    policy_chunks = [
        {"chunk_id": r["chunk_id"], "doc_id": r["doc_id"], "clause": r["clause"],
         "applicability": r["applicability"], "text": r["text"]}
        for r in pol["results"]
    ]
    return {"found": True, "projected": projected, "policy_says": policy,
            "recorded": repo.recorded_refunds(ctx.conn, booking_id),
            "sources": policy["sources"], "policy_chunks": policy_chunks}


def quote_late_fee(ctx: ToolContext, booking_id: str) -> dict:
    """Late fee: policy_says vs recorded late-fee penalty rows."""
    b = _booking(ctx.conn, booking_id)
    if b is None:
        return _not_found(booking_id)
    v = _vehicle(ctx.conn, b["vehicle_id"])
    tier = _customer_tier(ctx.conn, b["customer_id"])
    if not b["actual_return_at"]:
        policy = {"fee": None, "steps": ["Vehicle not yet returned; no late fee "
                                         "can be computed."], "sources": ["RW-POL-04 cl.1"]}
    else:
        minutes = int((engine.parse_db_utc(b["actual_return_at"])
                       - engine.parse_db_utc(b["scheduled_end"])).total_seconds() / 60)
        policy = engine.late_fee(minutes, v["hourly_rate"], tier)
    recorded = [p for p in repo.recorded_penalties(ctx.conn, booking_id)
                if "late" in (p["remarks"] or "").lower()]
    return {"found": True, "policy_says": policy, "recorded": recorded,
            "sources": policy["sources"]}


def quote_battery_fee(ctx: ToolContext, booking_id: str) -> dict:
    """EV battery fee: policy_says vs recorded battery penalty rows."""
    b = _booking(ctx.conn, booking_id)
    if b is None:
        return _not_found(booking_id)
    policy = engine.battery_fee(b["return_battery_pct"])
    recorded = [p for p in repo.recorded_penalties(ctx.conn, booking_id)
                if "battery" in (p["remarks"] or "").lower()]
    return {"found": True, "policy_says": policy, "recorded": recorded,
            "sources": policy["sources"]}


def search_policy(ctx: ToolContext, query: str, booking_id: str | None = None,
                  topic: str | None = None) -> dict:
    """Retrieve the relevant policy clauses for a question.

    If booking_id is given, its booked_at is used to decide which refund policy
    version applies (labelled in each result's applicability). Scope comes from
    the session; booking_id is only used to read booked_at within scope.
    """
    booked_at = None
    if booking_id:
        b = _booking(ctx.conn, booking_id)
        if b is not None:
            booked_at = b["booked_at"]
    from src.policy.retriever import search
    return search(query, booked_at=booked_at, topic=topic)


def run_sql(ctx: ToolContext, sql: str) -> dict:
    """Run one validated read-only SELECT against the role-scoped views.

    Execution errors (e.g. a wrong column name in model-written SQL) are returned
    as a structured error so the model can correct itself, rather than raising
    and failing the whole turn.
    """
    try:
        rows = run_query(ctx.conn, sql)
        return {"ok": True, "row_count": len(rows), "rows": rows, "sql": sql}
    except (SQLValidationError, TimeoutError) as exc:
        return {"ok": False, "error": str(exc), "sql": sql}
    except sqlite3.OperationalError as exc:
        return {"ok": False, "error": f"SQL error: {exc}. Check table/column "
                f"names against the schema and retry.", "sql": sql}


# --- registry ------------------------------------------------------------

_COMMON = ["get_booking", "get_payments_summary", "get_damage", "quote_rental",
           "quote_refund", "quote_late_fee", "quote_battery_fee", "search_policy",
           "run_sql"]
_CUSTOMER_ONLY = ["list_my_bookings"]

_CALLABLES = {
    "get_booking": get_booking, "list_my_bookings": list_my_bookings,
    "get_payments_summary": get_payments_summary, "get_damage": get_damage,
    "quote_rental": quote_rental, "quote_refund": quote_refund,
    "quote_late_fee": quote_late_fee, "quote_battery_fee": quote_battery_fee,
    "search_policy": search_policy, "run_sql": run_sql,
}

_BID = {"booking_id": {"type": "string", "description": "Booking id, e.g. B-0001"}}


def _schema(name: str, desc: str, props: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": required},
    }}


_SCHEMAS = {
    "get_booking": _schema("get_booking", "Fetch one booking with its vehicle.", _BID, ["booking_id"]),
    "list_my_bookings": _schema("list_my_bookings", "List the current customer's bookings.", {}, []),
    "get_payments_summary": _schema("get_payments_summary", "Rental paid plus recorded penalties and refunds.", _BID, ["booking_id"]),
    "get_damage": _schema("get_damage", "Damage reports for a booking, flagging billable ones.", _BID, ["booking_id"]),
    "quote_rental": _schema("quote_rental", "Compute rental charge, GST and deposit for a booking.", _BID, ["booking_id"]),
    "quote_refund": _schema("quote_refund", "Compute refund (policy) vs recorded refunds for a booking.", _BID, ["booking_id"]),
    "quote_late_fee": _schema("quote_late_fee", "Compute late fee (policy) vs recorded late fees.", _BID, ["booking_id"]),
    "quote_battery_fee": _schema("quote_battery_fee", "Compute EV battery fee (policy) vs recorded.", _BID, ["booking_id"]),
    "run_sql": _schema("run_sql", "Run one read-only SELECT over the allowed views.",
                       {"sql": {"type": "string", "description": "A single SELECT statement."}}, ["sql"]),
    "search_policy": _schema(
        "search_policy",
        "Retrieve policy clauses to answer any policy/eligibility/rules question "
        "(refunds, cancellation, late fees, grace, deposits, KYC, damage, GST, "
        "battery, charging). Use this instead of stating policy from memory. Not "
        "for computing amounts (use the quote_* tools) or reading booking data.",
        {"query": {"type": "string", "description": "The policy question."},
         "booking_id": {"type": "string", "description": "Optional booking to "
                        "decide which refund version applies."},
         "topic": {"type": "string", "description": "Optional topic hint, e.g. "
                   "refund, late_fee, deposit, kyc, battery, damage."}},
        ["query"]),
}


def build_tools(ctx: ToolContext):
    """Return (schemas, dispatch) for the session's role.

    dispatch(name, args) ignores any customer_id in args: scope comes from the
    session-bound connection, never from the model.
    """
    names = _COMMON + (_CUSTOMER_ONLY if ctx.session.role is Role.CUSTOMER else [])
    schemas = [_SCHEMAS[n] for n in names]

    def dispatch(name: str, args: dict) -> dict:
        if name not in names:
            return {"error": f"Tool {name!r} is not available for this role."}
        args = {k: v for k, v in (args or {}).items() if k != "customer_id"}
        return _CALLABLES[name](ctx, **args)

    return schemas, dispatch
