"""The retrieval half of the graph: route, specialist (fanned out per corpus), verify.

Does: two model calls (router, specialist) and the code-only quote check.
Does not: write the answer or touch memory. That is app/graph/nodes_answer.py.
"""
from langgraph.types import Send

from app import config
from app.graph import prompting
from app.ingest.index import Store
from app.llm import call_model, parse_json
from app.retrieve.hybrid import search

_store = None


def store() -> Store:
    """The index, loaded once per process."""
    global _store
    if _store is None:
        _store = Store()
    return _store


def trace_entry(node: str, corpus: str, prompt_file: str, system_text: str, user_text: str, reply: dict) -> dict:
    """One model call as the run log records it: prompts, response, tokens, seconds."""
    return {"node": node, "corpus": corpus, "prompt_file": prompt_file, "system_text": system_text,
            "user_text": user_text, "response": reply["text"], "input_tokens": reply["input_tokens"],
            "output_tokens": reply["output_tokens"], "seconds": reply["seconds"]}


def route(state: dict) -> dict:
    """Ask the model which of the three bodies the question touches, and a focused query for each."""
    system_text = prompting.load_prompt("router")
    user_text = (prompting.DATA_NOTE + prompting.turns_block(state.get("history", []))
                 + f"<question>\n{state['question']}\n</question>")
    reply = call_model(system_text, user_text, config.EFFORT_ROUTER)
    out = parse_json(reply["text"])
    # only known corpora survive; a made-up name is dropped rather than searched
    corpora = [c for c in out.get("corpora", []) if c in config.CORPORA]
    queries = {c: str(out.get("queries", {}).get(c) or state["question"]) for c in corpora}
    return {"corpora": corpora, "queries": queries, "router_reason": str(out.get("reason", "")),
            "steps_ran": ["route"],
            "trace": [trace_entry("route", "", "router.md", system_text, user_text, reply)]}


def fan_out(state: dict):
    """One Send per chosen corpus; straight to verify when the router chose nothing."""
    if not state["corpora"]:
        return "verify"
    return [Send("specialist", {"corpus": c, "query": state["queries"][c], "question": state["question"]})
            for c in state["corpora"]]


def specialist(payload: dict) -> dict:
    """Search one corpus, hand the chunks to that corpus's specialist prompt, collect findings or a refusal."""
    corpus = payload["corpus"]
    chunks = search(store(), payload["query"], corpus)
    for c in chunks:
        c["corpus"] = corpus
    system_text = prompting.load_prompt(f"specialist_{corpus}")
    user_text = (prompting.DATA_NOTE + prompting.chunks_block(chunks)
                 + f"<your_part>\n{payload['query']}\n</your_part>\n"
                 + f"<full_question>\n{payload['question']}\n</full_question>")
    reply = call_model(system_text, user_text, config.EFFORT_SPECIALIST)
    out = parse_json(reply["text"])
    refused = bool(out.get("refused")) or config.REFUSAL_STRING in reply["text"]
    report = {"corpus": corpus, "refused": refused, "reasoning": str(out.get("reasoning", "")),
              "chunks_seen": len(chunks), "findings": [] if refused else list(out.get("findings", []))}
    return {"specialist_outputs": [report], "raw_chunks": chunks, "steps_ran": [f"specialist:{corpus}"],
            "trace": [trace_entry("specialist", corpus, f"specialist_{corpus}.md", system_text, user_text, reply)]}


def verify_findings(raw_findings: list[dict], corpus: str, chunks_by_id: dict) -> tuple[list[dict], list[dict]]:
    """Code-only check: a finding survives only if its quote is a substring of the chunk it names."""
    kept, dropped = [], []
    for f in raw_findings:
        quote, chunk_id = str(f.get("quote", "")), str(f.get("chunk_id", ""))
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            dropped.append({"corpus": corpus, "chunk_id": chunk_id, "quote": quote, "reason": "chunk_id not among retrieved chunks"})
        elif not quote or quote not in chunk["text"]:
            dropped.append({"corpus": corpus, "chunk_id": chunk_id, "quote": quote, "reason": "quote is not a substring of that chunk"})
        else:
            kept.append({"corpus": corpus, "quote": quote, "source": chunk["source"], "title": chunk["title"],
                         "locator": chunk["locator"], "doc_date": chunk["doc_date"],
                         "why_it_matters": str(f.get("why_it_matters", "")), "verified": True,
                         "source_url": str(chunk.get("source_url", ""))})
    return kept, dropped


def verify(state: dict) -> dict:
    """Drop every quote that is not verbatim in its chunk. No model here; this is the one rule, in code."""
    chunks_by_id = {c["id"]: c for c in state.get("raw_chunks", [])}
    reports, dropped = [], []
    for raw in state.get("specialist_outputs", []):
        kept, gone = verify_findings(raw["findings"], raw["corpus"], chunks_by_id)
        dropped.extend(gone)
        reports.append({**raw, "findings": kept})
    return {"reports": reports, "dropped_quotes": dropped, "steps_ran": ["verify"]}
