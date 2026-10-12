"""Hybrid policy retrieval with code-driven v1/v2 handling.

BM25 always runs; embeddings are fused in (reciprocal rank fusion) only when the
index has them. Version selection between the two refund policies is decided by
code (engine.refund_version), never by similarity:

  - refund / cancellation / no-show queries ALWAYS return the best chunk(s) from
    BOTH RW-POL-02 (v1) and RW-POL-03 (v2) plus each one's Scope clause;
  - if booked_at is known, the applicable version is labelled "APPLIES to this
    booking" and the other "SUPERSEDED for this booking, shown for reference";
  - if booked_at is unknown, both are labelled with their date condition.

Late-fee/grace queries always include Annexure A; deposit queries include
RW-POL-01 clause 5.
"""
from __future__ import annotations

import re

from src.policy.index import embed_texts, get_index, tokenize
from src.rules.engine import refund_version

TOP_K = 5
BM25_MIN_SCORE = 1.0          # below this (and no forced family) -> not in policy
RRF_K = 60

CUTOFF_TEXT = "1 July 2026 00:00 IST"

_REFUND_FAMILY = re.compile(r"refund|cancel|no[- ]show|\bnsh\b|slab", re.I)
_LATE_FAMILY = re.compile(r"\blate\b|grace", re.I)
_DEPOSIT_FAMILY = re.compile(r"deposit", re.I)


def _rankings(query: str, idx) -> dict[int, float]:
    """Fused score per chunk index via reciprocal rank fusion."""
    bm25 = idx.bm25.get_scores(tokenize(query))
    order_bm25 = sorted(range(len(bm25)), key=lambda i: -bm25[i])
    fused: dict[int, float] = {i: 0.0 for i in range(len(bm25))}
    for rank, i in enumerate(order_bm25):
        fused[i] += 1.0 / (RRF_K + rank)

    if idx.embeddings is not None:
        import numpy as np
        q = embed_texts([query], idx.embed_model)
        if q is not None:
            qv = q[0] / (np.linalg.norm(q[0]) + 1e-9)
            mat = idx.embeddings / (np.linalg.norm(idx.embeddings, axis=1, keepdims=True) + 1e-9)
            cos = mat @ qv
            order_emb = sorted(range(len(cos)), key=lambda i: -cos[i])
            for rank, i in enumerate(order_emb):
                fused[i] += 1.0 / (RRF_K + rank)
    return fused, bm25


def _by(idx, doc_id=None, clause_prefix=None, clause=None):
    for i, c in enumerate(idx.chunks):
        if doc_id and c["doc_id"] != doc_id:
            continue
        if clause and c["clause"] != clause:
            continue
        if clause_prefix and not str(c["clause"]).startswith(clause_prefix):
            continue
        yield i, c


def _best_in(idx, fused, doc_id) -> int | None:
    cands = [i for i, _ in _by(idx, doc_id=doc_id)]
    return max(cands, key=lambda i: fused[i]) if cands else None


def _applicability(chunk: dict, booked_at: str | None) -> str:
    doc = chunk["doc_id"]
    if doc in ("RW-POL-02", "RW-POL-03"):
        if booked_at:
            applies = refund_version(booked_at)  # 'v1' or 'v2'
            mine = "v1" if doc == "RW-POL-02" else "v2"
            return ("APPLIES to this booking" if mine == applies
                    else "SUPERSEDED for this booking, shown for reference")
        return (f"applies only if booking made before {CUTOFF_TEXT}"
                if doc == "RW-POL-02"
                else f"applies only if booking made on or after {CUTOFF_TEXT}")
    return chunk.get("applies_to") or "applies to all rentals"


def search(query: str, booked_at: str | None = None, topic: str | None = None,
           k: int = TOP_K) -> dict:
    """Return up to k policy chunks with applicability notes, version-aware."""
    idx = get_index()
    fused, bm25 = _rankings(query, idx)

    q = f"{query} {topic or ''}"
    is_refund = bool(_REFUND_FAMILY.search(q))
    is_late = bool(_LATE_FAMILY.search(q))
    is_deposit = bool(_DEPOSIT_FAMILY.search(q))

    forced: list[int] = []

    def add(i):
        if i is not None and i not in forced:
            forced.append(i)

    if is_refund:
        # Force the actual slab tables (v1 in RW-POL-02 1.1, v2 in Annexure 1),
        # the best-scoring chunk from each policy, and each Scope clause.
        for i, _ in _by(idx, doc_id="RW-POL-02", clause="1.1"):
            add(i)
        for i, _ in _by(idx, doc_id="RW-POL-03", clause="Annexure 1"):
            add(i)
        add(_best_in(idx, fused, "RW-POL-02"))
        add(_best_in(idx, fused, "RW-POL-03"))
        for doc in ("RW-POL-02", "RW-POL-03"):
            for i, _ in _by(idx, doc_id=doc, clause="Scope"):
                add(i)
    if is_late:
        for i, _ in _by(idx, doc_id="RW-POL-04", clause="Annexure A"):
            add(i)
    if is_deposit:
        for i, _ in _by(idx, doc_id="RW-POL-01", clause_prefix="5"):
            add(i)

    # Ranked candidates by fused score.
    ranked = sorted(range(len(idx.chunks)), key=lambda i: -fused[i])

    if not forced and (len(bm25) == 0 or max(bm25) < BM25_MIN_SCORE):
        return {"results": [], "note": "no relevant policy found"}

    # Forced chunks first, then fill with top-ranked up to k (forced may exceed k).
    picked = list(forced)
    for i in ranked:
        if len(picked) >= max(k, len(forced)):
            break
        if i not in picked:
            picked.append(i)

    results = []
    for i in picked:
        c = idx.chunks[i]
        results.append({
            "chunk_id": c["chunk_id"], "doc_id": c["doc_id"],
            "version": c["version"], "clause": c["clause"], "kind": c["kind"],
            "applicability": _applicability(c, booked_at),
            "score": round(fused[i], 5), "text": c["text"],
        })
    return {"results": results, "note": None,
            "version_decided_by": ("booked_at" if booked_at else "unknown")}
