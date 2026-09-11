"""The routes, exactly as runs/INTERFACES.md lists them.

Does: translate HTTP bodies into service calls and return contract objects.
Does not: hold logic or touch the graph directly. Errors are turned into plain sentences in app/api/run.py.
"""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app import config
from app.contract import Answer, ManagerDecision
from app.graph import service
from app.graph.nodes import store
from app.memory import long_term

router = APIRouter()


class AskBody(BaseModel):
    thread_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class ResumeBody(BaseModel):
    thread_id: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    decided_by: str = Field(min_length=1)


@router.get("/health")
def health() -> dict:
    """Alive, and how many chunks the store holds."""
    return {"ok": True, "chunks": store().count()}


@router.post("/ask")
def ask(body: AskBody) -> Answer:
    """Run the graph for one question on a thread."""
    return service.ask(body.thread_id, body.text)


@router.post("/resume")
def resume(body: ResumeBody) -> Answer:
    """Continue a thread paused for a manager."""
    return service.resume(body.thread_id, body.answer, body.reason, body.decided_by)


@router.get("/thread/{thread_id}")
def thread(thread_id: str) -> dict:
    """Every turn on the thread and whether it is waiting."""
    return service.get_thread(thread_id)


@router.get("/escalations")
def escalations() -> list[dict]:
    """Threads waiting on a manager."""
    return service.list_escalations()


@router.get("/memory")
def memory() -> list[ManagerDecision]:
    """Every manager decision, newest first."""
    return long_term.list_decisions()


@router.get("/internal/selfcheck")
def selfcheck(x_internal_token: str = Header(default="")) -> dict:
    """Re-run the gates if app.selfcheck exists. Guarded by config.INTERNAL_TOKEN when it is set."""
    if config.INTERNAL_TOKEN and x_internal_token != config.INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="X-Internal-Token header does not match APP_INTERNAL_TOKEN")
    try:
        from app import selfcheck
    except ImportError:
        return {"gates": []}
    return selfcheck.run_all()
