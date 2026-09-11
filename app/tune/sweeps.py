"""Phase 7 sweeps: top_k, dense_weight, chunk size, overlap. Charts, csv, sweeps.json, config comments.

Does: python -m app.tune.sweeps. Chunking sweeps run on an in-memory subset, never the disk store.
Does not: change a config value unless a sweep shows a clear win; every change is printed.
"""
import json
import time

from app import config
from app.ingest.index import Store
from app.tune.charts import plot_sweep, write_csv
from app.tune.clock import append_report
from app.tune.decide import choose_all, write_comments
from app.tune.hit import resolve_hit_rate
from app.tune.refusal import wait_for_golden
from app.tune.subset import SubsetStore, doc_metadata, pick_pages, read_pages

EXTRA_PAGES = 150   # random pages beyond the golden ones, from the same documents


def sweep_top_k(store, golden, rate) -> list[dict]:
    """Page and doc hit rate as k grows, dense_weight fixed at config."""
    rows = []
    for k in [2, 4, 6, 8, 10, 15]:
        r = rate(store, golden, k, config.DENSE_WEIGHT)
        rows.append({"top_k": k, "page_hit_rate": r["page_hit_rate"], "doc_hit_rate": r["doc_hit_rate"]})
        print("  top_k", rows[-1], flush=True)
    return rows


def sweep_dense_weight(store, golden, rate) -> list[dict]:
    """Hit rate across the blend; 0.0 is BM25 alone, 1.0 is dense alone."""
    rows = []
    for w in [0.0, 0.25, 0.5, 0.75, 1.0]:
        r = rate(store, golden, config.TOP_K, w)
        rows.append({"dense_weight": w, "page_hit_rate": r["page_hit_rate"], "doc_hit_rate": r["doc_hit_rate"]})
        print("  dense_weight", rows[-1], flush=True)
    return rows


def subset_point(page_texts, doc_meta, golden, rate, size, overlap) -> dict:
    """One in-memory rebuild at (size, overlap), scored at config TOP_K and DENSE_WEIGHT."""
    started = time.time()
    sub = SubsetStore(page_texts, doc_meta, size, overlap, f"sub_{size}_{overlap}")
    try:
        r = rate(sub, golden, config.TOP_K, config.DENSE_WEIGHT)
    except Exception as err:
        # the eval agent's hit_rate may want the real Store; fall back to ours and say so
        from app.tune.hit import hit_rate
        print(f"  eval hit_rate failed on subset ({err}); using app.tune.hit.hit_rate", flush=True)
        r = hit_rate(sub, golden, config.TOP_K, config.DENSE_WEIGHT)
    row = {"chunk_size": size, "overlap": overlap, "page_hit_rate": r["page_hit_rate"],
           "doc_hit_rate": r["doc_hit_rate"], "total_chunks": sub.count(), "seconds": round(time.time() - started, 1)}
    sub.close()
    print("  subset", row, flush=True)
    return row


def main() -> None:
    """All four sweeps, then the charts, the json, the config comments and the log report."""
    store, golden = Store(), wait_for_golden()
    rate, rate_origin = resolve_hit_rate()
    print("hit rate from", rate_origin, flush=True)
    results = {"hit_rate_from": rate_origin, "top_k": sweep_top_k(store, golden, rate),
               "dense_weight": sweep_dense_weight(store, golden, rate)}
    # chunking sweeps: golden pages plus random pages from the same documents, rebuilt in memory
    pages = pick_pages(golden, store.metas, EXTRA_PAGES)
    page_texts, doc_meta = read_pages(pages), doc_metadata(store.metas)
    results["subset_pages"] = len(pages)
    print(f"subset: {len(pages)} pages from {len({s for s, _ in pages})} documents", flush=True)
    results["chunk_size"] = [subset_point(page_texts, doc_meta, golden, rate, s, 150) for s in [400, 800, 1200, 1600]]
    results["overlap"] = [subset_point(page_texts, doc_meta, golden, rate, 1200, o) for o in [0, 75, 150, 300]]
    chosen = choose_all(results)
    results["chosen"] = chosen
    n, q = len(pages), sum(1 for g in golden if g["bucket"] != "unanswerable")
    results["charts"] = [
        plot_sweep("top_k", results["top_k"], "top_k", f"top_k sweep, full store, {q} answerable golden questions", chosen["TOP_K"]["value"]),
        plot_sweep("dense_weight", results["dense_weight"], "dense_weight", f"dense_weight sweep at top_k {config.TOP_K}, full store, {q} answerable golden questions", chosen["DENSE_WEIGHT"]["value"]),
        plot_sweep("chunk_size", results["chunk_size"], "chunk_size", f"chunk size sweep, {n}-page subset, overlap 150", chosen["CHUNK_SIZE"]["value"]),
        plot_sweep("overlap", results["overlap"], "overlap", f"overlap sweep, {n}-page subset, size 1200", chosen["CHUNK_OVERLAP"]["value"]),
        write_csv("top_k", results["top_k"]), write_csv("dense_weight", results["dense_weight"]),
        write_csv("chunk_size", results["chunk_size"]), write_csv("overlap", results["overlap"]),
    ]
    results["config_lines"] = write_comments(chosen)
    with open(config.RUNS_DIR / "sweeps.json", "w") as f:
        json.dump(results, f, indent=1)
    for line in results["config_lines"]:
        print(line)
    changes = [k for k, c in chosen.items() if c["changed"]] or ["none"]
    append_report("sweeps", {
        "CLOCK": "see heading",
        "DONE": f"4 sweeps, 4 charts in charts/, runs/sweeps.json; chunking on a {n}-page subset; hit rate from {rate_origin}",
        "NOW": "config.py comments rewritten; handing back to the parent",
        "DECIDED": "value changes: " + ", ".join(changes) + "; " + "; ".join(c["reason"] for c in chosen.values()),
        "SAY": chosen["TOP_K"]["say"],
        "IF BEHIND": "nothing left to cut; the sweeps are done",
    })


if __name__ == "__main__":
    main()
