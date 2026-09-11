"""A small in-memory store rebuilt at any chunk size and overlap, for the chunking sweeps.

Does: pick the golden pages plus random pages from the same documents, re-read them with pypdf,
      rechunk with app.ingest.chunk.chunk_text, index in RAM with Chroma (cosine) and BM25.
Does not: touch store/ on disk. Every collection here is temporary.
"""
import csv
import random

import chromadb
from pypdf import PdfReader
from rank_bm25 import BM25Okapi

from app import config
from app.ingest.chunk import chunk_text
from app.ingest.index import tokenize


def source_paths() -> dict[str, str]:
    """File name -> path under data/raw, from the manifest."""
    with open(config.MANIFEST_PATH, newline="") as f:
        return {row["file"].split("/")[-1]: row["file"] for row in csv.DictReader(f)}


def pick_pages(golden: list[dict], store_metas: list[dict], extra: int, seed: int = 7) -> list[tuple[str, str]]:
    """Every golden (source, locator) plus `extra` random other pages from the same documents."""
    wanted = {(s["source"], s["locator"]) for g in golden for s in g.get("expected_sources", [])}
    docs = {source for source, _ in wanted}
    pool = sorted({(m["source"], m["locator"]) for m in store_metas if m["source"] in docs} - wanted)
    random.Random(seed).shuffle(pool)
    return sorted(wanted | set(pool[:extra]))


def read_pages(pages: list[tuple[str, str]]) -> dict[tuple[str, str], str]:
    """Page text by (source, locator), read once with pypdf."""
    paths, readers, out = source_paths(), {}, {}
    for source, locator in pages:
        if source not in readers:
            readers[source] = PdfReader(str(config.RAW_DIR / paths[source]))
        page_number = int(locator.split()[1]) - 1
        out[(source, locator)] = readers[source].pages[page_number].extract_text() or ""
    return out


class SubsetStore:
    """Looks like app.ingest.index.Store to search(): collection, bm25, ids, metas, texts, by_id."""

    def __init__(self, page_texts: dict, doc_meta: dict, size: int, overlap: int, name: str):
        self.ids, self.metas, self.texts = [], [], []
        # rechunk every page at this setting, carrying the same metadata shape as the real store
        for (source, locator), text in page_texts.items():
            for n, piece in enumerate(chunk_text(text, size, overlap)):
                self.ids.append(f"{source}::{locator}::{n}")
                self.metas.append({**doc_meta[source], "locator": locator, "chunk_on_page": n})
                self.texts.append(piece)
        if not self.ids:
            raise ValueError("subset produced no chunks")
        self.bm25 = BM25Okapi([tokenize(t) for t in self.texts])
        self.by_id = {i: n for n, i in enumerate(self.ids)}
        self.client = chromadb.Client()
        self.collection = self.client.create_collection(name, metadata={"hnsw:space": config.CHROMA_SPACE})
        for i in range(0, len(self.ids), 500):
            self.collection.add(ids=self.ids[i:i + 500], documents=self.texts[i:i + 500], metadatas=self.metas[i:i + 500])

    def count(self) -> int:
        return len(self.ids)

    def close(self) -> None:
        """Free the in-memory collection so the next setting starts clean."""
        self.client.delete_collection(self.collection.name)


def doc_metadata(store_metas: list[dict]) -> dict[str, dict]:
    """Document-level fields (title, corpus, date...) per source, copied from the real store."""
    out = {}
    for m in store_metas:
        if m["source"] not in out:
            out[m["source"]] = {k: v for k, v in m.items() if k not in ("locator", "chunk_on_page")}
    return out
