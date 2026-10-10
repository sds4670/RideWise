"""Tests for time handling. These pass today and anchor the UTC->IST contract."""
from datetime import datetime, timezone

from src.rules.time_utils import IST, format_ist, parse_db_utc, to_ist


def test_parse_db_utc_is_aware_utc():
    dt = parse_db_utc("2026-06-30 18:30:00")
    assert dt == datetime(2026, 6, 30, 18, 30, tzinfo=timezone.utc)


def test_parse_db_utc_handles_none_and_blank():
    assert parse_db_utc(None) is None
    assert parse_db_utc("   ") is None


def test_to_ist_adds_530():
    # 18:30 UTC on 2026-06-30 is exactly the v2 cutoff: 2026-07-01 00:00 IST.
    dt = to_ist(parse_db_utc("2026-06-30 18:30:00"))
    assert (dt.year, dt.month, dt.day, dt.hour, dt.minute) == (2026, 7, 1, 0, 0)
    assert dt.utcoffset() == IST.utcoffset(None)


def test_format_ist_is_labelled():
    assert format_ist("2026-08-14 05:10:00") == "2026-08-14 10:40 IST"


def test_format_ist_missing():
    assert format_ist(None) == "not recorded"
