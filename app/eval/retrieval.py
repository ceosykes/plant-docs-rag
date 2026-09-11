"""Retrieval hit rate over the golden set, plus a random baseline to compare against.

Does: for each answerable question and each expected corpus, run hybrid search and check
whether the expected page (page_hit) or at least the expected document (doc_hit) came back.
A question hits when every expected corpus hits; inside one corpus any listed source counts.
Does not: call a model. Pure retrieval, so the tune agent can sweep it cheaply.
"""
import json
import random

from app import config
from app.ingest.index import Store
from app.retrieve.hybrid import search


def load_golden() -> list[dict]:
    """Read app/eval/golden.json; raise if it is missing or empty."""
    path = config.ROOT / "app" / "eval" / "golden.json"
    if not path.exists():
        raise FileNotFoundError(f"expected golden set at {path}")
    with open(path) as f:
        golden = json.load(f)
    if not golden:
        raise ValueError(f"golden set at {path} is empty")
    return golden


def sources_in(item: dict, corpus: str, store: Store) -> list[dict]:
    """Expected sources of one question that live in this corpus, by the store's own tags."""
    corpus_of = {m["source"]: m["corpus"] for m in store.metas}
    return [s for s in item["expected_sources"] if corpus_of.get(s["source"]) == corpus]


def corpus_hits(chunks: list[dict], expected: list[dict]) -> tuple[bool, bool]:
    """(page_hit, doc_hit) for one corpus: any expected source matched at page or doc level."""
    page = any(c["source"] == e["source"] and c["locator"] == e["locator"] for c in chunks for e in expected)
    doc = any(c["source"] == e["source"] for c in chunks for e in expected)
    return page, doc


def score_question(item: dict, fetch, store: Store) -> dict:
    """Run fetch(question, corpus) per expected corpus and fold the corpus hits into one row."""
    page_ok, doc_ok, seen = True, True, {}
    for corpus in item["expected_corpora"]:
        chunks = fetch(item["question"], corpus)
        page, doc = corpus_hits(chunks, sources_in(item, corpus, store))
        page_ok, doc_ok = page_ok and page, doc_ok and doc
        seen[corpus] = [f"{c['source']} {c['locator']}" for c in chunks]
    return {"id": item["id"], "bucket": item["bucket"], "shape": item["shape"],
            "page_hit": int(page_ok), "doc_hit": int(doc_ok), "returned": seen}


def summarize(rows: list[dict]) -> dict:
    """Overall and per-bucket rates from the per-question rows. Empty input gives zeros."""
    def rate(subset, key):
        return round(sum(r[key] for r in subset) / len(subset), 3) if subset else 0.0
    per_bucket = {}
    for bucket in sorted({r["bucket"] for r in rows}):
        sub = [r for r in rows if r["bucket"] == bucket]
        per_bucket[bucket] = {"page_hit_rate": rate(sub, "page_hit"), "doc_hit_rate": rate(sub, "doc_hit"), "n": len(sub)}
    return {"page_hit_rate": rate(rows, "page_hit"), "doc_hit_rate": rate(rows, "doc_hit"),
            "per_bucket": per_bucket, "per_question": rows, "n": len(rows)}


def hit_rate(store: Store, golden: list[dict], top_k: int, dense_weight: float, chunk_size=None) -> dict:
    """Hybrid search hit rates on the answerable questions. chunk_size is accepted for the
    tune agent's sweeps (the store passed in already carries that size) and is not used here."""
    answerable = [g for g in golden if g["bucket"] != "unanswerable"]

    def fetch(question, corpus):
        return search(store, question, corpus, top_k, dense_weight)

    return summarize([score_question(g, fetch, store) for g in answerable])


def random_baseline(store: Store, golden: list[dict], top_k: int, draws: int = 20, seed: int = 7) -> dict:
    """Same shape as hit_rate, but top_k chunks drawn at random from the right corpus, averaged over draws."""
    answerable = [g for g in golden if g["bucket"] != "unanswerable"]
    by_corpus = {c: [n for n, m in enumerate(store.metas) if m["corpus"] == c] for c in config.CORPORA}
    rng = random.Random(seed)

    def fetch(question, corpus):
        picks = rng.sample(by_corpus[corpus], min(top_k, len(by_corpus[corpus])))
        return [store.metas[n] for n in picks]

    # one summary per draw, then average the rates; per_question keeps the last draw for inspection
    runs = [summarize([score_question(g, fetch, store) for g in answerable]) for _ in range(draws)]
    out = runs[-1]
    out["page_hit_rate"] = round(sum(r["page_hit_rate"] for r in runs) / draws, 3)
    out["doc_hit_rate"] = round(sum(r["doc_hit_rate"] for r in runs) / draws, 3)
    for bucket in out["per_bucket"]:
        out["per_bucket"][bucket]["page_hit_rate"] = round(sum(r["per_bucket"][bucket]["page_hit_rate"] for r in runs) / draws, 3)
        out["per_bucket"][bucket]["doc_hit_rate"] = round(sum(r["per_bucket"][bucket]["doc_hit_rate"] for r in runs) / draws, 3)
    out["draws"] = draws
    return out
