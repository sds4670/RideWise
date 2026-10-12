"""Structure-aware chunking of the policy documents.

One chunk = one numbered clause, one heading section, one table, or one FAQ Q&A.
Tables are never split by row. A clause keeps its worked example with it. No
fixed-size windows and no overlap. Each chunk text starts with a context header
so it stands alone, and carries metadata (doc, version, applicability, clause,
kind, topic tags).

The two scanned annexures (v2 refund schedule, tier grace) have no extractable
PDF text, so they come from the hand-transcribed src/policy/annexes.md, which is
treated as authoritative for those two image pages.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

from pypdf import PdfReader

from src.config import DATA_DIR, PROJECT_ROOT

ANNEXES = PROJECT_ROOT / "src" / "policy" / "annexes.md"

# doc_id, title, version, effective_from, applies_to (applicability note).
DOC_META = {
    "01_Rental_Agreement_and_Terms.pdf": dict(
        doc_id="RW-POL-01", title="Rental Agreement and Terms", version="3.0",
        effective_from="2025-01-01", applies_to="all rentals"),
    "02_Cancellation_and_Refund_Policy_v1.pdf": dict(
        doc_id="RW-POL-02", title="Cancellation and Refund Policy v1", version="v1",
        effective_from="2025-01-01",
        applies_to="bookings made before 2026-07-01 00:00 IST"),
    "03_Cancellation_and_Refund_Policy_v2.pdf": dict(
        doc_id="RW-POL-03", title="Cancellation and Refund Policy v2", version="v2",
        effective_from="2026-07-01",
        applies_to="bookings made on or after 2026-07-01 00:00 IST"),
    "04_Late_Return_and_Damage_Penalty_Schedule.pdf": dict(
        doc_id="RW-POL-04", title="Late Return and Damage Penalty Schedule",
        version="2.1", effective_from="2025-01-01", applies_to="all rentals"),
    "05_EV_User_Guide_and_FAQ.pdf": dict(
        doc_id="RW-POL-05", title="EV User Guide and FAQ", version="1.4",
        effective_from=None, applies_to="EV scooters and EV bikes"),
}

# Topic tags derived from content, not per-question hardcoding.
_TAG_PATTERNS = {
    "refund": r"refund",
    "cancellation": r"cancel",
    "no_show": r"no[- ]show|\bNSH\b",
    "late_fee": r"late (return|fee|hour)|lateness",
    "grace": r"grace",
    "battery": r"battery|low[- ]battery",
    "deposit": r"deposit",
    "kyc": r"\bKYC\b|know your customer",
    "damage": r"damage|claim|lost key",
    "gst": r"\bGST\b",
    "ev_charging": r"charg",
    "tiers": r"\btier\b|GOLD|SILVER|STANDARD",
    "rental_charge": r"rental charge|daily rate|hourly rate|per 24",
}


@dataclass
class Chunk:
    doc_id: str
    doc_title: str
    version: str
    effective_from: str | None
    applies_to: str | None
    clause: str
    kind: str                       # clause | table | example | faq
    tags: list[str] = field(default_factory=list)
    body: str = ""                  # text without the header
    chunk_id: str = ""

    @property
    def header(self) -> str:
        bits = [self.doc_id, self.doc_title]
        if self.effective_from:
            bits.append(f"effective {self.effective_from}")
        if self.applies_to:
            bits.append(f"applies to {self.applies_to}")
        bits.append(f"clause {self.clause}")
        return "[" + " | ".join(bits) + "]"

    @property
    def text(self) -> str:
        return f"{self.header}\n{self.body}".strip()

    @property
    def tokens_est(self) -> int:
        return max(1, len(self.text) // 4)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("body", None)
        d["text"] = self.text
        d["tokens_est"] = self.tokens_est
        return d


# --- text extraction -----------------------------------------------------

def _clean_lines(raw: str, title: str) -> list[str]:
    drop = [
        re.compile(r"^RW-POL-0\d\b"),
        re.compile(r"^RideWise Mobility Pvt\. Ltd\."),
        re.compile(r"^Page \d+\s*$"),
        re.compile(r"^Document RW-POL-0\d"),
        re.compile(r"^\s*$"),
        re.compile(rf"^{re.escape(title)}\s*$"),
        re.compile(r"^Figure \d+:"),            # figure captions
        re.compile(r"^Scanned copy"),           # annex image caption
    ]
    out = []
    for ln in raw.splitlines():
        s = ln.strip()
        if any(p.search(s) for p in drop):
            continue
        out.append(s)
    return out


def _extract(path: Path, title: str) -> list[str]:
    reader = PdfReader(str(path))
    lines: list[str] = []
    for page in reader.pages:
        lines += _clean_lines(page.extract_text() or "", title)
    return lines


# --- clause splitting ----------------------------------------------------

_SUBCLAUSE = re.compile(r"^(\d+\.\d+(?:\.\d+)?)\s+(.*)")
_SECTION = re.compile(r"^(\d+)\.\s+([A-Z][A-Za-z].*)")
_NAMED = re.compile(r"^(Scope|Why it changed|Contact|Authorised signatory)\b", re.I)
_ANNEX = re.compile(r"^Annexure\s+(\w+)", re.I)


def _tags_for(text: str) -> list[str]:
    low = text.lower()
    tags = [t for t, pat in _TAG_PATTERNS.items() if re.search(pat, text if t in ("kyc", "gst", "tiers", "no_show") else low, re.I)]
    return tags


def _kind_for(clause: str, body: str) -> str:
    low = body.lower()
    if clause.lower().startswith("faq"):
        return "faq"
    rows = len(re.findall(r"₹\s?\d", body))
    # A worked example mentions "example" AND carries rupee figures.
    if "example" in low and "₹" in body:
        return "example"
    # Several aligned rate/percent rows, or an enum table, is a table.
    if rows >= 3 or (body.count("%") >= 3):
        return "table"
    if re.search(r"\b(VERIFIED|PENDING|REJECTED)\b", body) and body.count("\n") >= 2:
        return "table"
    return "clause"


def _split_clauses(lines: list[str], meta: dict) -> list[Chunk]:
    chunks: list[Chunk] = []
    cur_clause: str | None = None
    buf: list[str] = []
    skipping_annex = False

    def flush():
        nonlocal buf, cur_clause
        if cur_clause is None:
            buf = []
            return
        body = "\n".join(buf).strip()
        # Skip pure headings with no real body.
        if body and len(body) > 3:
            chunks.append(_mk(meta, cur_clause, body))
        buf = []

    for ln in lines:
        if _ANNEX.match(ln):
            # Scanned annex content comes from annexes.md; skip PDF version.
            flush()
            cur_clause = None
            skipping_annex = True
            continue
        if skipping_annex:
            continue
        m = _SUBCLAUSE.match(ln)
        # A real clause body starts with a capital (sentence); table decimals
        # like "3.7 kWh" start lowercase and must NOT be treated as clauses.
        if m and (m.group(2) == "" or m.group(2)[:1].isupper()):
            flush()
            cur_clause = m.group(1)
            buf = [m.group(2)]
            continue
        m = _SECTION.match(ln)
        if m:
            flush()
            cur_clause = m.group(1) + "."
            buf = [m.group(2)]
            continue
        m = _NAMED.match(ln)
        if m:
            flush()
            cur_clause = m.group(1).title()
            buf = [ln]
            continue
        buf.append(ln)
    flush()
    return chunks


def _mk(meta: dict, clause: str, body: str, kind: str | None = None) -> Chunk:
    c = Chunk(
        doc_id=meta["doc_id"], doc_title=meta["title"], version=meta["version"],
        effective_from=meta["effective_from"], applies_to=meta["applies_to"],
        clause=clause, kind=kind or _kind_for(clause, body), body=body,
    )
    c.tags = _tags_for(body + " " + clause)
    c.chunk_id = f"{meta['doc_id']}#{clause}".replace(" ", "_")
    return c


# --- FAQ handling (RW-POL-05) --------------------------------------------

def _split_faq(chunks: list[Chunk], meta: dict) -> list[Chunk]:
    out: list[Chunk] = []
    for ch in chunks:
        if ch.doc_id == "RW-POL-05" and ch.clause.startswith("5") and "Q." in ch.body:
            parts = re.split(r"(?m)^(?=Q\.)", ch.body)
            for p in parts:
                p = p.strip()
                if not p.startswith("Q."):
                    continue
                q = p.splitlines()[0][3:].strip().rstrip("?")
                short = (q[:40]).strip()
                out.append(_mk(meta, f"FAQ: {short}", p, kind="faq"))
        else:
            out.append(ch)
    return out


# --- annexes.md ----------------------------------------------------------

def _annex_chunks() -> list[Chunk]:
    if not ANNEXES.exists():
        return []
    text = ANNEXES.read_text(encoding="utf-8")
    out: list[Chunk] = []
    specs = [
        ("## Annexure 1", DOC_META["03_Cancellation_and_Refund_Policy_v2.pdf"],
         "Annexure 1", ["refund", "cancellation"]),
        ("## Annexure A", DOC_META["04_Late_Return_and_Damage_Penalty_Schedule.pdf"],
         "Annexure A", ["late_fee", "grace", "tiers"]),
    ]
    for i, (marker, meta, clause, tags) in enumerate(specs):
        start = text.find(marker)
        if start == -1:
            continue
        end = text.find("\n## ", start + 1)
        body = text[start:(end if end != -1 else len(text))].strip()
        ch = _mk(meta, clause, body, kind="table")
        # annexes.md tags are explicit (transcribed tables).
        ch.tags = sorted(set(ch.tags) | set(tags))
        out.append(ch)
    return out


# --- public API ----------------------------------------------------------

def build_chunks() -> list[Chunk]:
    chunks: list[Chunk] = []
    for fname, meta in DOC_META.items():
        path = DATA_DIR / fname
        if not path.exists():
            continue
        lines = _extract(path, meta["title"])
        doc_chunks = _split_clauses(lines, meta)
        doc_chunks = _split_faq(doc_chunks, meta)
        chunks += doc_chunks
    chunks += _annex_chunks()
    return [c for c in chunks if not _is_bare_heading(c)]


def _is_bare_heading(c: Chunk) -> bool:
    """A section number whose body is just its title (<=6 words) carries nothing."""
    return bool(re.match(r"^\d+\.$", c.clause)) and len(c.body.split()) <= 6


def write_inventory() -> dict:
    chunks = build_chunks()
    out = PROJECT_ROOT / "docs" / "CHUNKS.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    by_doc: dict[str, int] = {}
    lines = ["# Chunk inventory", "",
             "| doc | clause | kind | tokens | tags | first 80 chars |",
             "|-----|--------|------|--------|------|----------------|"]
    for c in chunks:
        by_doc[c.doc_id] = by_doc.get(c.doc_id, 0) + 1
        preview = c.body.replace("\n", " ")[:80].replace("|", "/")
        lines.append(f"| {c.doc_id} | {c.clause} | {c.kind} | {c.tokens_est} | "
                     f"{','.join(c.tags)} | {preview} |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return by_doc


if __name__ == "__main__":
    counts = write_inventory()
    total = sum(counts.values())
    for doc in sorted(counts):
        print(f"{doc}: {counts[doc]} chunks")
    print(f"TOTAL: {total} chunks -> docs/CHUNKS.md")
