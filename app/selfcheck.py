"""Re-run the cheap gates on demand and say each result in plain words with the number.

Does: store count, corpus filter changes the answer, fabricated quote dropped, proofs and eval
numbers reread from runs/. Does not: call the model (that is the eval, four minutes).
"""
import json

from app import config
from app.ingest.index import Store
from app.retrieve.hybrid import search


def gate(name: str, passed: bool, number, plain: str) -> dict:
    return {"name": name, "passed": bool(passed), "number": number, "plain": plain}


def check_store(store: Store) -> dict:
    n = store.count()
    return gate("index", n > 1000, n, f"{n:,} pieces of the documents are indexed and ready to search.")


def check_filter(store: Store) -> dict:
    q = "the pump seal is leaking, can I open it while it runs"
    m = search(store, q, "maintenance", 3)
    s = search(store, q, "safety", 3)
    ok = m and s and m[0]["source"] != s[0]["source"]
    return gate("corpus filter", ok, f"{m[0]['source'] if m else '-'} vs {s[0]['source'] if s else '-'}",
                "The same question asked of the maintenance shelf and the safety shelf returns two different documents.")


def check_verify() -> dict:
    from app.graph.nodes import verify_findings
    chunk = {"id": "c1", "text": "Check belt tension after the first 24 hours of run-in."}
    fake = {"quote": "Check belt tension every 6 months.", "chunk_id": "c1"}
    kept, dropped = verify_findings([fake], "maintenance", {"c1": chunk})
    return gate("quote check", len(kept) == 0 and len(dropped) == 1, len(dropped),
                "A made-up quote that is not in the document was thrown out before anyone saw it.")


def check_proofs() -> list[dict]:
    path = config.RUNS_DIR / "proofs.json"
    if not path.exists():
        return [gate("proofs", False, "-", "The proofs have not been run yet.")]
    p = json.loads(path.read_text())
    out = []
    gap = p.get("refusal", {}).get("gap")
    if gap is not None:
        out.append(gate("refusal by score", gap <= 0, round(gap, 3),
                        "A similarity score cannot tell an answerable question from an unanswerable one here, so the system refuses in words, not by a number."))
    ov = p.get("overlap", {}).get("mean_shared")
    if ov is not None:
        out.append(gate("chunk overlap", abs(ov - config.CHUNK_OVERLAP) < 10, round(ov, 1),
                        f"Neighbouring pieces of a page really do share about {config.CHUNK_OVERLAP} characters."))
    return out


def check_eval() -> list[dict]:
    path = config.RUNS_DIR / "eval_results.json"
    if not path.exists():
        return [gate("eval", False, "-", "The test set has not been run yet.")]
    e = json.loads(path.read_text())
    r = e.get("retrieval", {})
    hit, base = r.get("hybrid", {}).get("page_hit_rate"), r.get("random_baseline", {}).get("page_hit_rate")
    out = [gate("finds the right page", (hit or 0) > (base or 0) * 5, f"{hit} vs random {base}",
                "On the test questions the right page is found far more often than picking pages at random.")]
    g = e.get("generation", {})
    if g:
        un = (g.get("per_bucket", {}) or {}).get("unanswerable", {})
        out.append(gate("refuses when it should", un.get("correct", 0) == 1.0, un.get("correct"),
                        "Every question the documents cannot answer was sent to a manager instead of guessed."))
    return out


def run_all() -> dict:
    store = Store()
    gates = [check_store(store), check_filter(store)]
    try:
        gates.append(check_verify())
    except Exception as e:
        gates.append(gate("quote check", False, "-", f"Could not run the quote check: {e}"))
    gates += check_proofs() + check_eval()
    return {"gates": gates}
