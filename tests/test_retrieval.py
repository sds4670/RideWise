"""Retrieval hit-rate and code-driven v1/v2 version handling."""
import pytest

from src.policy.retriever import search

# (query, booked_at, [acceptable (doc_id, clause_prefix)])
CASES = [
    ("gold tier grace period for late return", None, [("RW-POL-04", "Annexure A")]),
    ("version 2 refund 48 hours 75 percent", None, [("RW-POL-03", "Annexure 1")]),
    ("version 1 refund 24 hours 50 percent", None, [("RW-POL-02", "1.1")]),
    ("security deposit for a scooter rental of 24 hours", None, [("RW-POL-01", "5")]),
    ("security deposit for a bike", None, [("RW-POL-01", "5")]),
    ("can I rent if my KYC is pending", None, [("RW-POL-01", "2")]),
    ("is a no-show refunded", None,
     [("RW-POL-01", "7"), ("RW-POL-02", "3"), ("RW-POL-03", "3")]),
    ("EV returned late and below 10 percent both fees", None,
     [("RW-POL-04", "2"), ("RW-POL-05", "FAQ")]),
    ("exactly 10 percent battery at return fee", None, [("RW-POL-04", "2")]),
    ("battery runs out during trip towing", None, [("RW-POL-05", "FAQ")]),
    ("is GST refunded in proportion on a refund", None,
     [("RW-POL-01", "4.3"), ("RW-POL-02", "1.2"), ("RW-POL-03", "1.2")]),
    ("minimum rental duration whole hours", None, [("RW-POL-01", "3.2")]),
    ("lost keys charge", None, [("RW-POL-04", "3.2")]),
    ("damage claim status charged to customer", None, [("RW-POL-04", "3.1")]),
    ("late fee 1.5 times hourly rate part hour", None, [("RW-POL-04", "1.2")]),
    ("late fee for KTM Duke model", None, [("RW-POL-04", "1.5")]),
    ("rental charge daily rate cap", None, [("RW-POL-01", "4")]),
    ("how long do refunds take to process", None,
     [("RW-POL-02", "4"), ("RW-POL-03", "4")]),
    ("can I charge the EV at home", None, [("RW-POL-05", "FAQ")]),
    ("must I wear a helmet", None, [("RW-POL-01", "8")]),
    ("deposit returns not shown in records gateway", None, [("RW-POL-01", "5")]),
]


def _hit(query, booked_at, acceptable, k=4):
    res = search(query, booked_at=booked_at)["results"][:k]
    return any(
        any(r["doc_id"] == d and str(r["clause"]).startswith(c) for r in res)
        for d, c in acceptable
    )


def test_retrieval_hit_rate_at_4():
    hits = sum(_hit(q, ba, acc) for q, ba, acc in CASES)
    rate = hits / len(CASES)
    # At least 20 of the questions must have an expected clause in the top 4.
    assert hits >= 20, f"only {hits}/{len(CASES)} hit@4"
    assert rate >= 0.90


def test_offtopic_returns_not_in_policy():
    assert search("what is the weather in paris")["note"] == "no relevant policy found"


# --- version handling (decided by code) ----------------------------------

def _docs(results):
    return {r["doc_id"] for r in results}


def test_refund_without_booking_returns_both_versions_labelled():
    r = search("how much refund if I cancel before pickup")
    res = r["results"]
    assert "RW-POL-02" in _docs(res) and "RW-POL-03" in _docs(res)
    labels = {x["doc_id"]: x["applicability"] for x in res}
    assert "before" in labels["RW-POL-02"]
    assert "on or after" in labels["RW-POL-03"]


def test_boundary_1829_is_v1_and_1830_is_v2():
    before = search("refund if I cancel", booked_at="2026-06-30 18:29:59")["results"]
    after = search("refund if I cancel", booked_at="2026-06-30 18:30:00")["results"]
    lb = {x["doc_id"]: x["applicability"] for x in before}
    la = {x["doc_id"]: x["applicability"] for x in after}
    assert "APPLIES" in lb["RW-POL-02"] and "SUPERSEDED" in lb["RW-POL-03"]
    assert "APPLIES" in la["RW-POL-03"] and "SUPERSEDED" in la["RW-POL-02"]


def test_B1163_v1_applies_and_B1165_v2_applies():
    # Real booked_at values (UTC) for the two boundary bookings.
    r63 = search("refund", booked_at="2026-06-30 17:45:00")["results"]
    r65 = search("refund", booked_at="2026-06-30 20:15:00")["results"]
    l63 = {x["doc_id"]: x["applicability"] for x in r63}
    l65 = {x["doc_id"]: x["applicability"] for x in r65}
    assert "APPLIES" in l63["RW-POL-02"]      # B-1163 -> v1
    assert "APPLIES" in l65["RW-POL-03"]      # B-1165 -> v2
