"""Pick a value per sweep and phrase the evidence line that goes beside it in config.py.

Does: smallest k past the plateau; best blend; best chunking, current kept unless clearly beaten.
Does not: change CHUNK_SIZE or CHUNK_OVERLAP values. The disk store was built at 1200/150 and a
          change there means a 3-minute re-ingest, so a win is reported in the comment, not applied.
"""
from app import config
from app.tune.comments import rewrite_config

ONE_QUESTION = 1 / 18   # 18 answerable golden questions; a win smaller than one question is noise


def rate_at(rows: list[dict], key: str, value) -> float:
    """Page hit rate at one setting."""
    return next(r["page_hit_rate"] for r in rows if r[key] == value)


def choose_top_k(rows: list[dict]) -> dict:
    """Smallest k after which the next grid point gains no more than one question: the knee."""
    k = rows[-1]["top_k"]
    for here, after in zip(rows, rows[1:]):
        if after["page_hit_rate"] - here["page_hit_rate"] <= ONE_QUESTION + 1e-9:
            k = here["top_k"]
            break
    at_k, at_now, top = rate_at(rows, "top_k", k), rate_at(rows, "top_k", config.TOP_K), rows[-1]
    evidence = (f"page hit {at_k:.2f} at k={k} on the golden set, {at_now:.2f} at {config.TOP_K}; "
                f"the curve flattens after {k}, k={top['top_k']} reaches {top['page_hit_rate']:.2f} for far more chunks")
    return {"value": k, "changed": k != config.TOP_K, "evidence": evidence,
            "reason": f"TOP_K {k}: knee of the curve, {at_now:.2f} at {config.TOP_K} to {at_k:.2f} at {k}",
            "say": f"Page hit rate goes from {at_now:.2f} at k={config.TOP_K} to {at_k:.2f} at k={k} and flattens there."}


def choose_dense_weight(rows: list[dict]) -> dict:
    """Best blend; the current 0.5 stays unless another point beats it by more than one question."""
    current = rate_at(rows, "dense_weight", config.DENSE_WEIGHT)
    best = max(rows, key=lambda r: r["page_hit_rate"])
    value = best["dense_weight"] if best["page_hit_rate"] > current + ONE_QUESTION else config.DENSE_WEIGHT
    bm25, dense = rate_at(rows, "dense_weight", 0.0), rate_at(rows, "dense_weight", 1.0)
    evidence = (f"page hit {rate_at(rows, 'dense_weight', value):.2f} at {value}; BM25 alone {bm25:.2f}, "
                f"dense alone {dense:.2f}; best point {best['dense_weight']} at {best['page_hit_rate']:.2f}")
    return {"value": value, "changed": value != config.DENSE_WEIGHT, "evidence": evidence,
            "reason": f"DENSE_WEIGHT {value}: BM25 alone {bm25:.2f}, dense alone {dense:.2f}"}


def choose_chunking(rows: list[dict], key: str, current_value: int, n_pages: int) -> dict:
    """Report the best point on the subset; the value stays because the disk store is built at it."""
    current = rate_at(rows, key, current_value)
    best = max(rows, key=lambda r: r["page_hit_rate"])
    chunks = {r[key]: r["total_chunks"] for r in rows}
    clear_win = best["page_hit_rate"] > current + ONE_QUESTION and best[key] != current_value
    if clear_win:
        note = f"{best[key]} scored {best['page_hit_rate']:.2f} ({chunks[best[key]]} chunks); a change needs a 3-minute re-ingest"
    else:
        low, high = min(r["page_hit_rate"] for r in rows), best["page_hit_rate"]
        note = f"grid {rows[0][key]}..{rows[-1][key]} spans {low:.2f}..{high:.2f}, within one question; chunk count {min(chunks.values())}..{max(chunks.values())}"
    evidence = f"page hit {current:.2f} at {current_value} on a {n_pages}-page subset, {chunks[current_value]} chunks; {note}"
    return {"value": current_value, "changed": False, "evidence": evidence, "clear_win_elsewhere": clear_win,
            "reason": f"{key} {current_value}: kept, store built at it; {note}"}


def choose_all(results: dict) -> dict:
    """One decision per tunable, keyed by the config name."""
    n = results["subset_pages"]
    return {"TOP_K": choose_top_k(results["top_k"]),
            "DENSE_WEIGHT": choose_dense_weight(results["dense_weight"]),
            "CHUNK_SIZE": choose_chunking(results["chunk_size"], "chunk_size", config.CHUNK_SIZE, n),
            "CHUNK_OVERLAP": choose_chunking(results["overlap"], "overlap", config.CHUNK_OVERLAP, n)}


def write_comments(chosen: dict) -> list[str]:
    """Rewrite the five value lines in config.py, the proof line for CHROMA_SPACE included."""
    lines = {name: (repr(c["value"]), c["evidence"]) for name, c in chosen.items()}
    lines["CHROMA_SPACE"] = ('"cosine"', "PROOF: stored vector norms are 1.0, so cosine, l2 and ip rank identically "
                             "(l2 = 2 x cosine distance, same order on 200 chunks); cosine because 0..2 reads as a similarity")
    return rewrite_config(lines)
