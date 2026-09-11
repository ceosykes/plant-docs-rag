"""The four calls the API and the eval make: ask, resume, get_thread, list_escalations.

Does: run the compiled graph on a thread, read its checkpoint, write a run log.
Does not: build prompts or touch the store. Nodes do that.
"""
from datetime import datetime, timezone

from langgraph.types import Command

from app import config
from app.contract import Answer
from app.graph import run_log
from app.graph.build import compiled
from app.graph.state import fresh_turn


def thread_config(thread_id: str) -> dict:
    """The LangGraph config that names the thread."""
    if not thread_id.strip():
        raise ValueError("thread_id is empty")
    return {"configurable": {"thread_id": thread_id}}


def is_waiting(snapshot) -> bool:
    """True when the graph is paused at the escalate interrupt on this thread."""
    return any(task.interrupts for task in snapshot.tasks)


def waiting_answer(values: dict) -> Answer:
    """The Answer a supervisor sees while a manager has the question."""
    return Answer(thread_id=values["thread_id"], status="waiting_for_manager", text=config.ESCALATION_TEXT,
                  corpora_chosen=values.get("corpora", []), router_reason=values.get("router_reason", ""),
                  reports=values.get("reports", []), memory_used=values.get("memory_used", []),
                  steps_ran=list(values.get("steps_ran", [])) + ["escalate"],
                  answered_at=datetime.now(timezone.utc))


def answer_from(snapshot) -> Answer:
    """The Answer for the current state: the waiting one, or the last completed turn."""
    if is_waiting(snapshot):
        return waiting_answer(snapshot.values)
    history = snapshot.values.get("history", [])
    if not history:
        raise RuntimeError("graph finished without writing an answer; check runs/ for the last run file")
    return Answer(**history[-1]["answer"])


def ask(thread_id: str, text: str) -> Answer:
    """Run the graph for one question. If the thread is already waiting on a manager, return that instead of starting again."""
    if not text.strip():
        raise ValueError("question text is empty")
    graph, cfg = compiled(), thread_config(thread_id)
    if is_waiting(graph.get_state(cfg)):
        return waiting_answer(graph.get_state(cfg).values)
    graph.invoke(fresh_turn(thread_id, text, datetime.now(timezone.utc).isoformat()), cfg)
    snapshot = graph.get_state(cfg)
    answer = answer_from(snapshot)
    run_log.write(thread_id, snapshot.values, answer.model_dump(mode="json"), "ask")
    return answer


def resume(thread_id: str, answer: str, reason: str, decided_by: str) -> Answer:
    """Continue a paused thread with the manager's words. Nothing before the interrupt runs again."""
    graph, cfg = compiled(), thread_config(thread_id)
    if not is_waiting(graph.get_state(cfg)):
        raise ValueError(f"thread {thread_id!r} is not waiting for a manager; nothing to resume")
    graph.invoke(Command(resume={"answer": answer, "reason": reason, "decided_by": decided_by}), cfg)
    snapshot = graph.get_state(cfg)
    result = answer_from(snapshot)
    run_log.write(thread_id, snapshot.values, result.model_dump(mode="json"), "resume")
    return result


def get_thread(thread_id: str) -> dict:
    """Every turn on the thread from the checkpoint, plus whether it is waiting at an interrupt."""
    snapshot = compiled().get_state(thread_config(thread_id))
    values = snapshot.values or {}
    turns = [{"question": t["question"], "answer": Answer(**t["answer"])} for t in values.get("history", [])]
    waiting = is_waiting(snapshot)
    if waiting:
        turns.append({"question": values["question"], "answer": waiting_answer(values)})
    return {"thread_id": thread_id, "turns": turns, "waiting": waiting}


def list_escalations() -> list[dict]:
    """Every thread paused at the escalate interrupt: thread_id, question, asked_at."""
    graph = compiled()
    thread_ids = {cp.config["configurable"]["thread_id"] for cp in graph.checkpointer.list(None)}
    out = []
    for thread_id in sorted(thread_ids):
        snapshot = graph.get_state(thread_config(thread_id))
        if is_waiting(snapshot):
            out.append({"thread_id": thread_id, "question": snapshot.values.get("question", ""),
                        "asked_at": snapshot.values.get("asked_at", "")})
    return out


def list_threads() -> list[dict]:
    """Every thread the checkpointer knows, newest first, for the evaluation tab."""
    graph = compiled()
    thread_ids = {cp.config["configurable"]["thread_id"] for cp in graph.checkpointer.list(None)}
    out = []
    for thread_id in thread_ids:
        snapshot = graph.get_state(thread_config(thread_id))
        values = snapshot.values or {}
        history = values.get("history") or []
        status = "waiting_for_manager" if is_waiting(snapshot) else (values.get("status") or "answered")
        out.append({"thread_id": thread_id, "first_question": (history[0]["question"] if history else values.get("question", "")),
                    "status": status, "turns": len(history), "asked_at": values.get("asked_at", "")})
    return sorted(out, key=lambda t: t["asked_at"], reverse=True)
