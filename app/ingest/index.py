"""The store: Chroma (cosine, set explicitly) plus a BM25 index saved as JSON.

Does: build both from a chunk list, load both for retrieval.
Does not: decide what to retrieve. That is app/retrieve/hybrid.py.
"""
import json
from pathlib import Path

import chromadb
from rank_bm25 import BM25Okapi

from app import config


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens. BM25 needs the same function at build and query time."""
    return [t for t in "".join(c if c.isalnum() else " " for c in text.lower()).split() if len(t) > 1]


def open_collection(reset: bool = False):
    """Cosine is set here because Chroma defaults to squared L2 (measured, see TOOLS.md)."""
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    if reset:
        try:
            client.delete_collection(config.COLLECTION)
        except Exception:
            pass
    return client.get_or_create_collection(config.COLLECTION, metadata={"hnsw:space": config.CHROMA_SPACE})


def write_store(chunks: list[dict]) -> None:
    """Chroma gets text plus metadata; BM25 gets tokens plus ids, saved beside it."""
    if not chunks:
        raise ValueError("no chunks to write; ingest found nothing")
    collection = open_collection(reset=True)
    ids = [f"{c['source']}::{c['locator']}::{c['chunk_on_page']}" for c in chunks]
    metas = [{k: v for k, v in c.items() if k != "text"} for c in chunks]
    # Chroma takes at most a few thousand rows per add on some builds; batch to be safe
    for i in range(0, len(chunks), 500):
        collection.add(ids=ids[i:i + 500], documents=[c["text"] for c in chunks[i:i + 500]], metadatas=metas[i:i + 500])
    config.BM25_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(config.BM25_PATH, "w") as f:
        json.dump({"ids": ids, "tokens": [tokenize(c["text"]) for c in chunks], "metas": metas,
                   "texts": [c["text"] for c in chunks]}, f)


class Store:
    """Both indexes loaded once. Retrieval asks this object, never the disk."""

    def __init__(self):
        if not config.BM25_PATH.exists():
            raise FileNotFoundError(f"no index at {config.BM25_PATH}; run: python -m app.ingest.run")
        with open(config.BM25_PATH) as f:
            saved = json.load(f)
        self.ids, self.metas, self.texts = saved["ids"], saved["metas"], saved["texts"]
        self.bm25 = BM25Okapi(saved["tokens"])
        self.collection = open_collection()
        self.by_id = {i: n for n, i in enumerate(self.ids)}

    def count(self) -> int:
        return len(self.ids)
