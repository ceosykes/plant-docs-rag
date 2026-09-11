"""Proof c: can a dense similarity threshold separate unanswerable from answerable questions?

Does: best dense similarity per golden question, then min(unanswerable) minus max(answerable).
Does not: run a model. Refusal stays a generator string unless this gap is positive.
"""
import json
import time

from app import config
from app.retrieve.hybrid import search

GOLDEN_PATH = config.ROOT / "app" / "eval" / "golden.json"


def wait_for_golden(timeout_s: int = 360, poll_s: int = 15) -> list[dict]:
    """Poll for the eval agent's golden set. Raises with the path if it never lands."""
    waited = 0
    while waited <= timeout_s:
        if GOLDEN_PATH.exists():
            with open(GOLDEN_PATH) as f:
                golden = json.load(f)
            if golden:
                return golden
        print(f"  waiting for {GOLDEN_PATH.name} ({waited}s)", flush=True)
        time.sleep(poll_s)
        waited += poll_s
    raise FileNotFoundError(f"{GOLDEN_PATH} did not appear within {timeout_s}s")


def corpora_for(item: dict) -> tuple[str, ...]:
    """Unanswerable questions search everything; the rest search where the answer should be."""
    if item["bucket"] == "unanswerable" or not item.get("expected_corpora"):
        return config.CORPORA
    return tuple(item["expected_corpora"])


def best_dense(store, item: dict) -> float:
    """Highest dense similarity any retrieved chunk reaches for this question."""
    best = 0.0
    for corpus in corpora_for(item):
        for hit in search(store, item["question"], corpus, config.TOP_K, 1.0):
            best = max(best, hit["dense"])
    return best


def prove_refusal(store, golden: list[dict]) -> dict:
    """Gap between the weakest unanswerable and the strongest answerable best-dense score."""
    answerable = [best_dense(store, g) for g in golden if g["bucket"] != "unanswerable"]
    unanswerable = [best_dense(store, g) for g in golden if g["bucket"] == "unanswerable"]
    if not answerable or not unanswerable:
        raise ValueError(f"golden set needs both buckets; got {len(answerable)} answerable, {len(unanswerable)} unanswerable")
    gap = round(min(unanswerable) - max(answerable), 4)
    if gap > 0:
        verdict = f"gap {gap} > 0: a threshold between {max(answerable)} and {min(unanswerable)} could work"
    else:
        verdict = f"gap {gap} <= 0: no threshold separates them; refusal stays the explicit {config.REFUSAL_STRING} string from the generator"
    return {"questions": len(golden), "answerable": len(answerable), "unanswerable": len(unanswerable),
            "max_answerable_dense": round(max(answerable), 4), "min_unanswerable_dense": round(min(unanswerable), 4),
            "mean_answerable_dense": round(sum(answerable) / len(answerable), 4),
            "mean_unanswerable_dense": round(sum(unanswerable) / len(unanswerable), 4),
            "gap": gap, "verdict": verdict}
