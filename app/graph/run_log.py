"""Writes runs/run_<thread_id>_<n>.json after every ask or resume.

Does: record the tunables in effect, the router output, retrieved chunks with scores, prompts, responses, tokens and timings.
Does not: hold secrets. runs/ is gitignored.
"""
import json

from app import config

TUNABLES = ("MODEL", "MODEL_TIMEOUT_S", "MODEL_MAX_TOKENS", "EFFORT_ROUTER", "EFFORT_SPECIALIST", "EFFORT_CUSTOMER",
            "CHUNK_SIZE", "CHUNK_OVERLAP", "TOP_K", "DENSE_WEIGHT", "CHROMA_SPACE", "MEMORY_MAX_ITEMS")


def next_path(thread_id: str):
    """runs/run_<thread_id>_<n>.json with n one past the files already there for this thread."""
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    existing = list(config.RUNS_DIR.glob(f"run_{thread_id}_*.json"))
    return config.RUNS_DIR / f"run_{thread_id}_{len(existing) + 1}.json"


def chunks_by_corpus(raw_chunks: list[dict]) -> dict:
    """Retrieved chunks grouped per corpus with source, page, scores and the text the agent saw."""
    out = {}
    for c in raw_chunks:
        out.setdefault(c["corpus"], []).append({"id": c["id"], "title": c["title"], "locator": c["locator"],
                                                "source": c["source"], "doc_date": c["doc_date"], "source_url": c.get("source_url", ""),
                                                "score": c["score"], "dense": c["dense"], "bm25": c["bm25"], "text": c["text"]})
    return out


def write(thread_id: str, values: dict, answer: dict, event: str) -> str:
    """Write one run file from the graph state and the Answer. Returns the path as a string."""
    record = {"event": event, "thread_id": thread_id, "question": values.get("question", ""),
              "config": {k: getattr(config, k) for k in TUNABLES},
              "router": {"corpora": values.get("corpora", []), "queries": values.get("queries", {}),
                         "reason": values.get("router_reason", "")},
              "retrieved": chunks_by_corpus(values.get("raw_chunks", [])),
              "dropped_quotes": values.get("dropped_quotes", []),
              "model_calls": values.get("trace", []),
              "steps_ran": values.get("steps_ran", []),
              "answer": answer}
    path = next_path(thread_id)
    path.write_text(json.dumps(record, indent=1, default=str))
    return str(path)
