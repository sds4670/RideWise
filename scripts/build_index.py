"""(Re)build the policy retrieval index.

Run:  python -m scripts.build_index

Prints the active mode (bm25 or bm25+embeddings), chunk count and build time.
Never writes to data/ or ridewise.db.
"""
from __future__ import annotations

from src.policy.index import build_index, embed_model


def main() -> None:
    model = embed_model()
    print(f"LLM_EMBED_MODEL: {'set (' + model + ')' if model else 'not set -> BM25 only'}")
    meta = build_index()
    print(f"mode:         {meta['mode']}")
    print(f"chunks:       {meta['n_chunks']}")
    print(f"build time:   {meta['build_seconds']}s")
    print(f"index dir:    index/ (chunks.jsonl, bm25.pkl"
          + (", embeddings.npy" if meta['mode'].endswith('embeddings') else "")
          + ", meta.json)")


if __name__ == "__main__":
    main()
