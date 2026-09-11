"""Page-level hit rate for the sweeps, and the resolver that prefers the eval agent's version.

Does: hit_rate(store, golden, top_k, dense_weight, chunk_size=None) -> dict, same signature as app.eval.retrieval.
Does not: judge answers. Retrieval only, no model.
"""
import importlib
import time

from app.retrieve.hybrid import search


def hit_rate(store, golden: list[dict], top_k: int, dense_weight: float, chunk_size=None) -> dict:
    """Share of answerable questions whose expected page (and document) lands in the top_k pool."""
    answerable = [g for g in golden if g["bucket"] != "unanswerable" and g.get("expected_sources")]
    if not answerable:
        raise ValueError("golden set has no answerable question with expected_sources")
    page_hits = doc_hits = 0
    for item in answerable:
        want_pages = {(s["source"], s["locator"]) for s in item["expected_sources"]}
        want_docs = {s["source"] for s in item["expected_sources"]}
        got = []
        for corpus in item["expected_corpora"]:
            got.extend(search(store, item["question"], corpus, top_k, dense_weight))
        page_hits += any((h["source"], h["locator"]) in want_pages for h in got)
        doc_hits += any(h["source"] in want_docs for h in got)
    return {"page_hit_rate": round(page_hits / len(answerable), 4), "doc_hit_rate": round(doc_hits / len(answerable), 4),
            "questions": len(answerable), "top_k": top_k, "dense_weight": dense_weight}


def resolve_hit_rate(timeout_s: int = 360, poll_s: int = 15):
    """The eval agent's hit_rate if it lands in time, else this module's. Returns (function, origin)."""
    waited = 0
    while waited <= timeout_s:
        try:
            module = importlib.import_module("app.eval.retrieval")
            return module.hit_rate, "app.eval.retrieval.hit_rate"
        except (ImportError, AttributeError):
            print(f"  waiting for app.eval.retrieval.hit_rate ({waited}s)", flush=True)
            time.sleep(poll_s)
            waited += poll_s
    return hit_rate, "app.tune.hit.hit_rate (eval agent's version never appeared)"
