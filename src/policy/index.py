"""Build and load the policy retrieval index.

Stores everything under index/ (gitignored), rebuilt from the chunks whenever a
hash of data/*.pdf + annexes.md changes:
  - chunks.jsonl : one chunk per line (with text + metadata)
  - bm25.pkl     : a pickled rank_bm25 index aligned to chunks.jsonl
  - embeddings.npy : optional, only if LLM_EMBED_MODEL is set
  - meta.json    : source hash, mode, embed model, counts

Never writes to data/ or ridewise.db. BM25 is always available; embeddings are
added only when the endpoint offers an embedding model (env LLM_EMBED_MODEL).
Local embedding models are never downloaded.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import pickle
import re
import time
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

from src.config import DATA_DIR, PROJECT_ROOT
from src.policy.chunker import ANNEXES, DOC_META, build_chunks

logger = logging.getLogger("ridewise.index")

INDEX_DIR = PROJECT_ROOT / "index"
CHUNKS_PATH = INDEX_DIR / "chunks.jsonl"
BM25_PATH = INDEX_DIR / "bm25.pkl"
EMB_PATH = INDEX_DIR / "embeddings.npy"
META_PATH = INDEX_DIR / "meta.json"

# Bump when chunking or tokenisation changes, so the index auto-rebuilds even
# though the source documents are unchanged.
INDEX_VERSION = "2"

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "of", "to",
    "in", "on", "for", "and", "or", "if", "my", "i", "you", "how", "what",
    "when", "which", "do", "does", "did", "can", "could", "will", "would",
    "with", "at", "by", "this", "that", "it", "me", "we", "as", "from", "about",
}


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS]


def embed_model() -> str | None:
    m = os.environ.get("LLM_EMBED_MODEL", "").strip()
    return m or None


# --- source hashing ------------------------------------------------------

def _source_hash() -> str:
    h = hashlib.sha256()
    h.update(INDEX_VERSION.encode())
    for fname in sorted(DOC_META):
        p = DATA_DIR / fname
        if p.exists():
            h.update(p.read_bytes())
    if ANNEXES.exists():
        h.update(ANNEXES.read_bytes())
    return h.hexdigest()


# --- embeddings ----------------------------------------------------------

def embed_texts(texts: list[str], model: str | None = None):
    """Embed texts via the endpoint. Returns a numpy array, or None if no model."""
    model = model or embed_model()
    if not model:
        return None
    import numpy as np
    from src.llm import get_client

    client = get_client()
    vecs = []
    for i in range(0, len(texts), 64):  # batch to stay well within limits
        resp = client.embeddings.create(model=model, input=texts[i:i + 64])
        vecs.extend(d.embedding for d in resp.data)
    return np.array(vecs, dtype="float32")


# --- build ---------------------------------------------------------------

def build_index() -> dict:
    """(Re)build the index from the current chunks. Returns meta."""
    start = time.monotonic()
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    chunks = [c.to_dict() for c in build_chunks()]
    with open(CHUNKS_PATH, "w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    corpus = [tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(corpus)
    with open(BM25_PATH, "wb") as fh:
        pickle.dump({"bm25": bm25, "ids": [c["chunk_id"] for c in chunks]}, fh)

    model = embed_model()
    mode = "bm25"
    if model:
        try:
            import numpy as np
            embs = embed_texts([c["text"] for c in chunks], model)
            np.save(EMB_PATH, embs)
            mode = "bm25+embeddings"
        except Exception as exc:  # noqa: BLE001 - fall back to BM25 only
            logger.warning("embedding build failed (%s); using BM25 only", exc)
            if EMB_PATH.exists():
                EMB_PATH.unlink()
            model = None
    elif EMB_PATH.exists():
        EMB_PATH.unlink()

    meta = {"hash": _source_hash(), "mode": mode, "embed_model": model,
            "n_chunks": len(chunks), "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "build_seconds": round(time.monotonic() - start, 2)}
    META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info("policy index built: %s", meta)
    return meta


# --- load ----------------------------------------------------------------

@dataclass
class PolicyIndex:
    chunks: list[dict]
    bm25: BM25Okapi
    ids: list[str]
    embeddings: object | None       # numpy array or None
    embed_model: str | None
    mode: str


_CACHE: PolicyIndex | None = None


def _is_fresh() -> bool:
    if not (META_PATH.exists() and CHUNKS_PATH.exists() and BM25_PATH.exists()):
        return False
    try:
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False
    return meta.get("hash") == _source_hash()


def get_index(force_rebuild: bool = False) -> PolicyIndex:
    """Load the index, auto-building on first run or when sources change."""
    global _CACHE
    if _CACHE is not None and not force_rebuild:
        return _CACHE
    if force_rebuild or not _is_fresh():
        build_index()

    chunks = [json.loads(line) for line in
              CHUNKS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    with open(BM25_PATH, "rb") as fh:
        payload = pickle.load(fh)
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))

    embeddings = None
    if meta.get("embed_model") and EMB_PATH.exists():
        import numpy as np
        embeddings = np.load(EMB_PATH)

    _CACHE = PolicyIndex(
        chunks=chunks, bm25=payload["bm25"], ids=payload["ids"],
        embeddings=embeddings, embed_model=meta.get("embed_model"),
        mode=meta.get("mode", "bm25"),
    )
    return _CACHE
