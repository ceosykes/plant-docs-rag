"""Dense plus BM25, fused, with the corpus filter applied before ranking.

Does: one function, search(store, question, corpus, top_k). Filter is a required argument.
Does not: rerank with a model. Not selected on the menu.
"""
from app import config
from app.ingest.index import Store, tokenize


def dense(store: Store, question: str, corpus: str, k: int) -> dict[str, float]:
    """Chroma with the corpus filter in the where clause, so the filter runs before ranking."""
    res = store.collection.query(query_texts=[question], n_results=k, where={"corpus": corpus})
    ids, dists = res["ids"][0], res["distances"][0]
    # cosine distance runs 0..2; 1 - distance is a similarity a human can read
    return {i: 1.0 - d for i, d in zip(ids, dists)}


def keyword(store: Store, question: str, corpus: str, k: int) -> dict[str, float]:
    """BM25 over the whole index, then keep only this corpus. Scores normalised to 0..1."""
    scores = store.bm25.get_scores(tokenize(question))
    ranked = sorted(range(len(scores)), key=lambda n: -scores[n])
    top = max(float(scores[ranked[0]]), 1e-9)
    out = {}
    for n in ranked:
        if store.metas[n]["corpus"] != corpus:
            continue
        out[store.ids[n]] = float(scores[n]) / top
        if len(out) >= k:
            break
    return out


def search(store: Store, question: str, corpus: str, top_k: int = config.TOP_K,
           dense_weight: float = config.DENSE_WEIGHT) -> list[dict]:
    """Fuse the two score maps by weighted sum. Returns chunks with text, metadata and both scores."""
    if corpus not in config.CORPORA:
        raise ValueError(f"corpus must be one of {config.CORPORA}, got {corpus!r}")
    if not question.strip():
        raise ValueError("question is empty")
    # retrieve wider than top_k from each so the fusion has something to reorder
    d, b = dense(store, question, corpus, top_k * 2), keyword(store, question, corpus, top_k * 2)
    fused = {i: dense_weight * d.get(i, 0.0) + (1 - dense_weight) * b.get(i, 0.0) for i in set(d) | set(b)}
    best = sorted(fused, key=lambda i: -fused[i])[:top_k]
    return [{"id": i, "text": store.texts[store.by_id[i]], **store.metas[store.by_id[i]],
             "score": round(fused[i], 4), "dense": round(d.get(i, 0.0), 4), "bm25": round(b.get(i, 0.0), 4)}
            for i in best]
