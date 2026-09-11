"""The eval entry point: python -m app.eval.run -> runs/eval_results.json plus a printed table.

Does: score retrieval (hit rate against a random baseline) and, when the graph exists,
generation (judge scores per bucket and per shape). The two are scored separately.
Does not: tune anything or fake a number. If ask() is not importable it says so and stops
after retrieval.
"""
import json
import time
from datetime import datetime, timezone

from app import config
from app.eval.judge import judge
from app.eval.retrieval import hit_rate, load_golden, random_baseline
from app.ingest.index import Store


def load_ask():
    """The graph's ask() if the graph agent has landed it, else None with the reason printed."""
    try:
        from app.graph.service import ask
        return ask
    except Exception as e:
        print(f"generation skipped: app.graph.service.ask not importable ({type(e).__name__}: {e})")
        return None


def generate_one(ask, item: dict) -> dict:
    """Ask the graph one golden question on its own thread and judge the Answer."""
    thread_id = f"eval-{item['id']}"
    started = time.time()
    answer = ask(thread_id, item["question"]).model_dump(mode="json")
    sources = [f"{f['source']} {f['locator']}" for r in answer["reports"] for f in r["findings"]]
    scores = judge(item, answer)
    return {"id": item["id"], "bucket": item["bucket"], "shape": item["shape"], "thread_id": thread_id,
            "status": answer["status"], "corpora_chosen": answer["corpora_chosen"],
            "finding_sources": sources, "answer_text": answer["text"], "seconds": round(time.time() - started, 1),
            **scores, "judge_reason": scores["reason"]}


def rates(rows: list[dict], group_key: str) -> dict:
    """Mean correct, grounded and plain_language per value of group_key (bucket or shape)."""
    out = {}
    for value in sorted({r[group_key] for r in rows}):
        sub = [r for r in rows if r[group_key] == value]
        out[value] = {k: round(sum(r[k] for r in sub) / len(sub), 3) for k in ("correct", "grounded", "plain_language")}
        out[value]["n"] = len(sub)
    return out


def generation_baseline(golden: list[dict]) -> dict:
    """The no-model floor: refuse everything. Scores 1 on unanswerable, 0 elsewhere."""
    rows = [{"bucket": g["bucket"], "shape": g["shape"], "correct": int(g["bucket"] == "unanswerable"),
             "grounded": int(g["bucket"] == "unanswerable"), "plain_language": 1} for g in golden]
    return {"rule": "refuse every question", "per_bucket": rates(rows, "bucket"), "per_shape": rates(rows, "shape")}


def run_generation(ask, golden: list[dict]) -> dict:
    """Every golden question through the graph and the judge, one row each. A crash on one question is recorded, not hidden."""
    rows = []
    for item in golden:
        try:
            rows.append(generate_one(ask, item))
        except Exception as e:
            rows.append({"id": item["id"], "bucket": item["bucket"], "shape": item["shape"], "status": "error",
                         "corpora_chosen": [], "finding_sources": [], "correct": 0, "grounded": 0,
                         "plain_language": 0, "judge_reason": f"{type(e).__name__}: {e}"})
        print(f"  {item['id']:4} {rows[-1]['status']:20} correct={rows[-1]['correct']} {rows[-1]['judge_reason'][:80]}")
    return {"per_bucket": rates(rows, "bucket"), "per_shape": rates(rows, "shape"), "per_question": rows,
            "n": len(rows), "baseline": generation_baseline(golden)}


def print_table(results: dict) -> None:
    """The compact table the gate reads out."""
    r, b = results["retrieval"]["hybrid"], results["retrieval"]["random_baseline"]
    print(f"\nRETRIEVAL (top_k={config.TOP_K}, dense_weight={config.DENSE_WEIGHT}, n={r['n']})")
    print(f"  {'bucket':8} {'page hit':>9} {'random':>7} {'doc hit':>9} {'random':>7}")
    print(f"  {'all':8} {r['page_hit_rate']:>9.3f} {b['page_hit_rate']:>7.3f} {r['doc_hit_rate']:>9.3f} {b['doc_hit_rate']:>7.3f}")
    for bucket, v in r["per_bucket"].items():
        rb = b["per_bucket"][bucket]
        print(f"  {bucket:8} {v['page_hit_rate']:>9.3f} {rb['page_hit_rate']:>7.3f} {v['doc_hit_rate']:>9.3f} {rb['doc_hit_rate']:>7.3f}")
    gen = results.get("generation")
    if not gen:
        print("\nGENERATION: not run")
        return
    print(f"\nGENERATION (n={gen['n']}, baseline = refuse everything)")
    print(f"  {'group':13} {'correct':>8} {'base':>6} {'grounded':>9} {'plain':>6}")
    for key in ("per_bucket", "per_shape"):
        for name, v in gen[key].items():
            base = gen["baseline"][key][name]["correct"]
            print(f"  {name:13} {v['correct']:>8.3f} {base:>6.3f} {v['grounded']:>9.3f} {v['plain_language']:>6.3f}")


def main() -> None:
    """Retrieval first, generation if the graph exists, one JSON file, one table."""
    store, golden = Store(), load_golden()
    results = {"ran_at": datetime.now(timezone.utc).isoformat(), "model": config.MODEL,
               "top_k": config.TOP_K, "dense_weight": config.DENSE_WEIGHT, "chunk_size": config.CHUNK_SIZE,
               "golden_n": len(golden),
               "retrieval": {"hybrid": hit_rate(store, golden, config.TOP_K, config.DENSE_WEIGHT),
                             "random_baseline": random_baseline(store, golden, config.TOP_K)}}
    ask = load_ask()
    if ask is not None:
        print(f"generation: {len(golden)} questions through the graph")
        results["generation"] = run_generation(ask, golden)
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.RUNS_DIR / "eval_results.json", "w") as f:
        json.dump(results, f, indent=1)
    print_table(results)
    print(f"\nwrote {config.RUNS_DIR / 'eval_results.json'}")


if __name__ == "__main__":
    main()
