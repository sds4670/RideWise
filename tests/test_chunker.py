"""Chunker: tables stay whole, every chunk has metadata and a header."""
from src.policy.chunker import build_chunks

CHUNKS = build_chunks()


def _find(doc_id, clause):
    return next((c for c in CHUNKS if c.doc_id == doc_id and c.clause == clause), None)


def test_annexure1_is_one_chunk_with_all_four_slabs():
    c = _find("RW-POL-03", "Annexure 1")
    assert c is not None
    for slab in ("48 hours", "12 hours", "2 hours", "Less than 2 hours"):
        assert slab in c.body
    for pct in ("100%", "75%", "25%"):
        assert pct in c.body


def test_annexureA_has_all_three_tiers():
    c = _find("RW-POL-04", "Annexure A")
    assert c is not None
    for tier in ("STANDARD", "SILVER", "GOLD"):
        assert tier in c.body


def test_late_fee_model_table_is_one_chunk():
    c = _find("RW-POL-04", "1.5")
    assert c is not None
    # Spans both PDF pages: first and last models present in a single chunk.
    assert "Royal Enfield Classic 350" in c.body
    assert "Oben Rorr" in c.body and "Ultraviolette F77" in c.body


def test_kyc_and_deposit_and_rental_tables_whole():
    kyc = _find("RW-POL-01", "2.1")
    assert all(s in kyc.body for s in ("VERIFIED", "PENDING", "REJECTED"))
    dep = _find("RW-POL-01", "5.1")
    assert "Bike" in dep.body and "Scooter" in dep.body
    assert "1,000" in dep.body and "500" in dep.body
    rent = _find("RW-POL-01", "4.2")
    assert "₹940" in rent.body or "940" in rent.body


def test_every_chunk_has_metadata_and_header():
    required = ("doc_id", "doc_title", "version", "applies_to", "clause", "kind",
                "tags", "chunk_id", "text", "tokens_est")
    for c in CHUNKS:
        d = c.to_dict()
        for field in required:
            assert field in d, f"{c.chunk_id} missing {field}"
        assert c.text.startswith("["), f"{c.chunk_id} has no context header"
        assert c.doc_id in c.text and str(c.clause) in c.text


def test_faq_split_one_per_question():
    faqs = [c for c in CHUNKS if c.kind == "faq"]
    assert len(faqs) >= 5
    assert all(c.body.strip().startswith("Q.") for c in faqs)
