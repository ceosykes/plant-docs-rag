"""The graph state: what one thread carries between nodes and between turns.

Does: name every field once, and give the fan-out fields a reducer so parallel specialists can both write.
Does not: hold logic. RESET at the head of a list starts that list fresh for a new turn on an old thread.
"""
from typing import Annotated, TypedDict

RESET = "__reset__"


def fresh_then_add(old: list, new: list) -> list:
    """List reducer. A list starting with RESET replaces the old list; otherwise it appends. Lets a thread reuse state per turn."""
    if new and new[0] == RESET:
        return list(new[1:])
    return list(old or []) + list(new or [])


class GraphState(TypedDict, total=False):
    thread_id: str
    question: str
    asked_at: str
    history: list[dict]           # completed turns on this thread: [{"question", "answer": Answer dict}]
    corpora: list[str]            # router's pick
    queries: dict                 # corpus -> focused search query
    router_reason: str
    specialist_outputs: Annotated[list[dict], fresh_then_add]   # one raw SpecialistReport dict per Send
    raw_chunks: Annotated[list[dict], fresh_then_add]           # every retrieved chunk, with corpus and scores
    reports: list[dict]           # SpecialistReport dicts after verify, only quotes that survived
    dropped_quotes: list[dict]    # {corpus, chunk_id, quote, reason}
    memory_used: list[str]
    next_step: str                # "escalate" or "customer_service", set by decide
    status: str
    answer_text: str
    steps_ran: Annotated[list[str], fresh_then_add]
    trace: Annotated[list[dict], fresh_then_add]                # one entry per model call: prompt, response, tokens, seconds


def fresh_turn(thread_id: str, question: str, asked_at: str) -> dict:
    """The input for one new question: resets the per-turn lists, keeps history from the checkpoint."""
    return {"thread_id": thread_id, "question": question, "asked_at": asked_at,
            "corpora": [], "queries": {}, "router_reason": "", "reports": [], "dropped_quotes": [],
            "memory_used": [], "next_step": "", "status": "", "answer_text": "",
            "specialist_outputs": [RESET], "raw_chunks": [RESET], "steps_ran": [RESET], "trace": [RESET]}
