"""Deterministic rules engine. All money math lives here, never in the LLM.

Every function is pure: it takes plain values, reads constants from
policy_rules.yaml, and returns a dict with the computed numbers, a
human-readable ``steps`` list, and the ``sources`` (policy doc + clause) that
applied. This lets the agent show its working and cite the policy for any figure.

Rounding: money is rounded to 2 decimals at the point a rupee value is produced.
"""
from __future__ import annotations

import math
from datetime import datetime

from src.rules.loader import load_policy
from src.rules.time_utils import IST, parse_db_utc

_P = load_policy()


def _money(x: float) -> float:
    return round(float(x), 2)


# --- GST -----------------------------------------------------------------

def gst(amount: float) -> dict:
    """GST on a taxable amount (rental, penalties, fees). RW-POL-01 cl.4.3."""
    rate = _P["gst_rate"]
    g = _money(amount * rate)
    return {
        "amount": _money(amount),
        "gst": g,
        "total": _money(amount + g),
        "steps": [f"GST at {int(rate * 100)}%: {_money(amount)} x {rate} = {g}"],
        "sources": ["RW-POL-01 cl.4.3"],
    }


# --- Booked duration -----------------------------------------------------

def booked_hours(scheduled_start_utc: str, scheduled_end_utc: str) -> dict:
    """Whole booked hours between two timestamps.

    Rentals are booked in whole hours (RW-POL-01 cl.3.2). If the span is not a
    whole number of hours, it is rounded up and ``whole`` is set False so the
    caller can flag the odd data rather than silently hide it.
    """
    start = parse_db_utc(scheduled_start_utc)
    end = parse_db_utc(scheduled_end_utc)
    raw = (end - start).total_seconds() / 3600.0
    whole = float(raw).is_integer()
    hours = int(raw) if whole else math.ceil(raw)
    return {"hours": hours, "raw_hours": round(raw, 4), "whole": whole}


# --- Rental charge -------------------------------------------------------

def rental_charge(hours: int, hourly_rate: float, daily_rate: float) -> dict:
    """Rental charge (ex-GST). RW-POL-01 cl.4.1.

    full_days*daily_rate + min(remaining_hours*hourly_rate, daily_rate).
    """
    min_hours = _P["rental"]["min_hours"]
    per_day = _P["rental"]["hours_per_day"]
    if hours < min_hours:
        hours = min_hours
    full_days, remaining = divmod(hours, per_day)
    day_part = full_days * daily_rate
    hour_part_raw = remaining * hourly_rate
    hour_part = min(hour_part_raw, daily_rate)
    charge = _money(day_part + hour_part)
    steps = [
        f"Booked {hours}h (min {min_hours}h) = {full_days} full day(s) + {remaining}h.",
        f"Day part: {full_days} x {daily_rate} = {_money(day_part)}.",
        f"Hour part: min({remaining} x {hourly_rate}, {daily_rate}) "
        f"= min({_money(hour_part_raw)}, {daily_rate}) = {_money(hour_part)}.",
        f"Rental charge (ex-GST): {charge}.",
    ]
    return {"charge": charge, "steps": steps, "sources": ["RW-POL-01 cl.4.1"]}


# --- Late fee ------------------------------------------------------------

def late_fee(minutes_late: int, hourly_rate: float, customer_tier: str) -> dict:
    """Late return fee (ex-GST). RW-POL-04 cl.1.2 and Annexure A (GOLD grace)."""
    multiplier = _P["late_fee"]["multiplier"]
    grace = _P["late_fee"]["grace_minutes_by_tier"].get(customer_tier, 0)
    sources = ["RW-POL-04 cl.1.2", "RW-POL-04 Annexure A"]

    if minutes_late <= 0:
        return {"fee": 0.0, "hours_charged": 0,
                "steps": ["Returned on time; no late fee."], "sources": sources}

    if grace and minutes_late <= grace:
        return {
            "fee": 0.0, "hours_charged": 0,
            "steps": [f"{customer_tier} grace is {grace} min; {minutes_late} min "
                      f"late is within grace, so no late fee."],
            "sources": sources,
        }

    hours_charged = math.ceil(minutes_late / 60)
    fee = _money(hours_charged * multiplier * hourly_rate)
    steps = []
    if grace:
        steps.append(f"{customer_tier} grace is {grace} min, but {minutes_late} min "
                     f"late exceeds it: full lateness is charged.")
    steps += [
        f"Late by {minutes_late} min -> {hours_charged} late hour(s) "
        f"(each part-hour rounds up).",
        f"Late fee (ex-GST): {hours_charged} x {multiplier} x {hourly_rate} = {fee}.",
    ]
    return {"fee": fee, "hours_charged": hours_charged, "steps": steps, "sources": sources}


# --- EV battery fee ------------------------------------------------------

def battery_fee(return_battery_pct: int | None) -> dict:
    """Low-battery fee (ex-GST). RW-POL-04 cl.2. Separate from any late fee."""
    threshold = _P["ev_battery_fee"]["threshold_pct"]
    flat = _P["ev_battery_fee"]["flat_fee"]
    sources = ["RW-POL-04 cl.2"]
    if return_battery_pct is None:
        return {"status": "unknown", "fee": None,
                "steps": ["Return battery level is not recorded, so the battery "
                          "fee cannot be determined. Say so rather than assuming."],
                "sources": sources}
    if return_battery_pct < threshold:
        return {"status": "applies", "fee": _money(flat),
                "steps": [f"Return battery {return_battery_pct}% is below "
                          f"{threshold}%: flat fee {flat} (ex-GST)."],
                "sources": sources}
    return {"status": "none", "fee": 0.0,
            "steps": [f"Return battery {return_battery_pct}% is {threshold}% or "
                      f"above: no battery fee."],
            "sources": sources}


# --- Deposit -------------------------------------------------------------

def deposit_due(vehicle_type: str, hours: int) -> dict:
    """Security deposit (no GST). RW-POL-01 cl.5.1."""
    rule = _P["deposit"].get(vehicle_type)
    sources = ["RW-POL-01 cl.5.1"]
    if rule is None:
        return {"deposit": 0.0,
                "steps": [f"No deposit rule for vehicle type {vehicle_type!r}."],
                "sources": sources}
    if hours >= rule["min_hours"]:
        amt = _money(rule["amount"])
        cond = ("any rental" if rule["min_hours"] == 0
                else f"rental >= {rule['min_hours']}h")
        return {"deposit": amt,
                "steps": [f"{vehicle_type}: deposit {amt} for {cond} "
                          f"({hours}h booked). No GST on deposits."],
                "sources": sources}
    return {"deposit": 0.0,
            "steps": [f"{vehicle_type}: deposit only for rentals >= "
                      f"{rule['min_hours']}h; {hours}h booked, so no deposit."],
            "sources": sources}


# --- Refund quote --------------------------------------------------------

def _cutoff_ist() -> datetime:
    raw = _P["refund"]["cutoff_ist"]
    return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)


def refund_version(booked_at_utc: str) -> str:
    """'v1' if booked before the IST cutoff, else 'v2'. RW-POL-02/03 scope."""
    booked_ist = parse_db_utc(booked_at_utc).astimezone(IST)
    return "v1" if booked_ist < _cutoff_ist() else "v2"


def _percent_for(version: str, hours_before: float) -> int:
    for slab in _P["refund"][version]:
        if hours_before >= slab["min_hours_before"]:
            return slab["percent"]
    return 0


def refund_quote(
    booked_at_utc: str,
    cancelled_at_utc: str,
    scheduled_start_utc: str,
    rental_paid_ex_gst: float,
    gst_paid: float,
    booking_status: str | None = None,
) -> dict:
    """Refund for a cancellation: version, lead time, percent, amounts, sources.

    RW-POL-02 (v1) / RW-POL-03 (v2). CNL_S is always 100%; NSH is always 0%.
    Percent applies to the rental actually paid; GST is refunded in proportion.
    """
    sources = ["RW-POL-02", "RW-POL-03"]

    if booking_status == "NSH":
        return _refund_result("n/a", 0, None, rental_paid_ex_gst, gst_paid,
                              ["No-show (NSH): no refund (RW-POL-01 cl.7.2)."],
                              ["RW-POL-01 cl.7.2"])
    if booking_status == "CNL_S":
        return _refund_result("n/a", 100, None, rental_paid_ex_gst, gst_paid,
                              ["Cancelled by RideWise (CNL_S): 100% refund."],
                              ["RW-POL-02 cl.2", "RW-POL-03 cl.2"])

    version = refund_version(booked_at_utc)
    start = parse_db_utc(scheduled_start_utc)
    cancelled = parse_db_utc(cancelled_at_utc)
    hours_before = (start - cancelled).total_seconds() / 3600.0
    percent = _percent_for(version, hours_before)

    booked_ist = parse_db_utc(booked_at_utc).astimezone(IST).strftime("%Y-%m-%d %H:%M")
    steps = [
        f"Booking made {booked_ist} IST -> policy {version} "
        f"(cutoff {_P['refund']['cutoff_ist']} IST).",
        f"Cancelled {round(hours_before, 2)}h before scheduled pickup.",
        f"{version} slab -> {percent}% of rental actually paid.",
    ]
    return _refund_result(version, percent, round(hours_before, 2),
                          rental_paid_ex_gst, gst_paid, steps, sources)


def _refund_result(version, percent, hours_before, rental_paid, gst_paid, steps, sources):
    rental_refund = _money(rental_paid * percent / 100)
    gst_refund = _money(gst_paid * percent / 100)
    total = _money(rental_refund + gst_refund)
    steps = steps + [
        f"Rental refund: {percent}% x {_money(rental_paid)} = {rental_refund}.",
        f"GST refund (same proportion): {percent}% x {_money(gst_paid)} = {gst_refund}.",
        f"Total refund: {total}.",
    ]
    return {
        "version": version,
        "percent": percent,
        "hours_before": hours_before,
        "rental_refund": rental_refund,
        "gst_refund": gst_refund,
        "total_refund": total,
        "steps": steps,
        "sources": sources,
    }
