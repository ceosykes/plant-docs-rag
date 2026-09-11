"""The answer half of the graph: recall_memory, decide, escalate (interrupt), customer_service.

Does: one model call (customer service) plus the code-only memory lookup, decision and manager hand-off.
Does not: retrieve or verify. Customer service only ever sees verified findings, never a chunk.
"""
from datetime import datetime, timezone

from langgraph.types import interrupt

from app import config
from app.contract import ManagerDecision
from app.graph import prompting
from app.graph.nodes import trace_entry
from app.llm import call_model
from app.memory import long_term


def finish(state: dict, node: str, status: str, text: str) -> dict:
    """Build the Answer for this turn and append it to the thread history. Shared by the two terminal nodes."""
    answer = {"thread_id": state["thread_id"], "status": status, "text": text,
              "corpora_chosen": state.get("corpora", []), "router_reason": state.get("router_reason", ""),
              "reports": state.get("reports", []), "memory_used": state.get("memory_used", []),
              "steps_ran": list(state.get("steps_ran", [])) + [node],
              "answered_at": datetime.now(timezone.utc).isoformat()}
    history = list(state.get("history", [])) + [{"question": state["question"], "answer": answer}]
    return {"status": status, "answer_text": text, "history": history, "steps_ran": [node]}


def recall_memory(state: dict) -> dict:
    """BM25 over past manager decisions; the top few become plain strings for context, never citations."""
    decisions = long_term.recall(state["question"])
    return {"memory_used": [prompting.decision_as_text(d) for d in decisions], "steps_ran": ["recall_memory"]}


def decide(state: dict) -> dict:
    """Code rule: no corpus chosen or every specialist refused, and no finding survived, means escalate."""
    reports = state.get("reports", [])
    survived = any(r["findings"] for r in reports)
    all_refused = bool(reports) and all(r["refused"] for r in reports)
    if survived and not all_refused:
        return {"next_step": "customer_service", "steps_ran": ["decide"]}
    return {"next_step": "escalate", "steps_ran": ["decide"]}


def next_step(state: dict) -> str:
    """Conditional edge: read what decide wrote."""
    return state["next_step"]


def escalate(state: dict) -> dict:
    """Pause the run for a manager; when they answer, save the decision once and mark the answer as from a person."""
    reports = state.get("reports", [])
    payload = {"question": state["question"], "corpora_searched": state.get("corpora", []),
               "came_back_empty": [r["corpus"] for r in reports if r["refused"] or not r["findings"]],
               "does_not_know": [r["reasoning"] for r in reports] or ["no document body matched this question"]}
    manager = interrupt(payload)
    # everything below runs only after the manager resumes the thread
    for field in ("answer", "reason", "decided_by"):
        if not str(manager.get(field, "")).strip():
            raise ValueError(f"manager resume is missing '{field}'; expected answer, reason and decided_by")
    decision = ManagerDecision(thread_id=state["thread_id"], question=state["question"], answer=manager["answer"],
                               reason=manager["reason"], decided_by=manager["decided_by"],
                               decided_at=datetime.now(timezone.utc))
    long_term.save_decision(decision)
    text = (f"Answer from your manager, {decision.decided_by} (a person, not a document): {decision.answer}\n"
            f"Reason given: {decision.reason}")
    return finish(state, "escalate", "answered_by_manager", text)


def forbidden_phrase(text: str) -> str:
    """The first config.FORBIDDEN_PATTERNS phrase found in the text, or an empty string."""
    lowered = text.lower()
    for phrase in config.FORBIDDEN_PATTERNS:
        if phrase in lowered:
            return phrase
    return ""


def customer_service(state: dict) -> dict:
    """Rewrite the verified findings for the supervisor at a fifth-grade level, then check for forbidden phrases in code."""
    system_text = prompting.load_prompt("customer_service")
    user_text = (prompting.DATA_NOTE + prompting.turns_block(state.get("history", []))
                 + prompting.memory_block(state.get("memory_used", []))
                 + prompting.findings_block(state.get("reports", []))
                 + f"<question>\n{state['question']}\n</question>")
    reply = call_model(system_text, user_text, config.EFFORT_CUSTOMER)
    text = reply["text"].strip()
    # the guardrail is checked in code after generation, not trusted to the prompt
    phrase = forbidden_phrase(text)
    if phrase:
        text = f"Answer withheld: it contained the phrase '{phrase}', which this system is not allowed to say. Ask your manager."
    out = finish(state, "customer_service", "answered", text)
    out["trace"] = [trace_entry("customer_service", "", "customer_service.md", system_text, user_text, reply)]
    return out
