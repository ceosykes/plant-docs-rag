"""Demo-surface routes: thread list and per-thread run records for the evaluation tab.

Does: read runs/run_<thread>_<n>.json and return them with prompts stripped.
Does not: return any system prompt or assembled prompt. Those never reach the browser.
"""
import json
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app import config
from app.graph import service

router = APIRouter()
SAFE_CALL_KEYS = ("node", "corpus", "response_text", "input_tokens", "output_tokens", "seconds")


def strip_prompts(record: dict) -> dict:
    """Keep what the panel shows; drop system_text and user prompts from every model call."""
    calls = []
    for c in record.get("model_calls", []):
        keep = {k: c.get(k) for k in SAFE_CALL_KEYS}
        keep["response_text"] = keep.get("response_text") or c.get("response") or ""
        calls.append(keep)
    return {k: v for k, v in record.items() if k != "model_calls"} | {"model_calls": calls}


@router.get("/threads")
def threads() -> list[dict]:
    return service.list_threads()


@router.get("/runs/{thread_id}")
def runs(thread_id: str) -> list[dict]:
    """All run records for one thread, in order of n."""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "", thread_id)
    files = sorted(config.RUNS_DIR.glob(f"run_{safe}_*.json"), key=lambda p: int(p.stem.rsplit("_", 1)[1]))
    return [strip_prompts(json.loads(p.read_text())) for p in files]


@router.get("/doc/{source}")
def doc(source: str) -> FileResponse:
    """The corpus PDF itself, so a citation link opens the real document at its page (#page=N)."""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "", source)
    matches = [p for p in config.RAW_DIR.rglob(safe) if p.is_file() and p.suffix.lower() == ".pdf"]
    if not matches:
        raise HTTPException(status_code=404, detail=f"no document called {safe!r} in the corpus")
    return FileResponse(matches[0], media_type="application/pdf", filename=safe, content_disposition_type="inline")
