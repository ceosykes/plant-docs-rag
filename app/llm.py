"""One model call, timed and counted, plus a JSON reader for what comes back.

Does: call_model(system, user, effort) -> text, tokens, seconds. parse_json(text) -> dict or list.
Does not: retry, stream, or hold a conversation. Every prompt is one system plus one user turn.
"""
import json
import os
import time

import anthropic

from app import config


def call_model(system_text: str, user_text: str, effort: str,
               max_tokens: int = config.MODEL_MAX_TOKENS) -> dict:
    """Send one prompt and return {text, input_tokens, output_tokens, seconds}. Raises with a next step."""
    if not system_text.strip() or not user_text.strip():
        raise ValueError("call_model needs a non-empty system_text and user_text")
    # this key is not scoped to a workspace, so the workspace id from .env rides along as a header
    headers = {"anthropic-workspace-id": os.environ["ANTHROPIC_WORKSPACE_ID"]} if os.environ.get("ANTHROPIC_WORKSPACE_ID") else {}
    client = anthropic.Anthropic(timeout=config.MODEL_TIMEOUT_S, default_headers=headers)
    started = time.time()
    try:
        response = client.messages.create(
            model=config.MODEL, max_tokens=max_tokens, system=system_text,
            messages=[{"role": "user", "content": user_text}],
            output_config={"effort": effort})
    except anthropic.AuthenticationError as e:
        raise RuntimeError(f"model rejected the API key; check ANTHROPIC_API_KEY in .env ({e})") from e
    except anthropic.RateLimitError as e:
        raise RuntimeError(f"model rate limited; wait a minute and retry ({e})") from e
    except anthropic.APITimeoutError as e:
        raise RuntimeError(f"model call passed {config.MODEL_TIMEOUT_S}s; lower TOP_K or shorten the prompt ({e})") from e
    except anthropic.APIStatusError as e:
        if "credit balance" in str(e.message).lower():
            raise RuntimeError("the answer service has no credits left; add credits to the Anthropic account and ask again") from e
        raise RuntimeError(f"model returned {e.status_code}; check config.MODEL={config.MODEL!r} ({e.message})") from e
    except anthropic.APIConnectionError as e:
        raise RuntimeError(f"could not reach the model API; check the network ({e})") from e
    # only text blocks count; anything else in the content list is ignored
    text = "".join(block.text for block in response.content if block.type == "text")
    return {"text": text, "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens, "seconds": round(time.time() - started, 2)}


def parse_json(text: str):
    """Find the first {...} or [...] in model text and load it. Raises ValueError naming what arrived."""
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not starts:
        raise ValueError(f"expected JSON from the model, got: {text[:200]!r}")
    first = min(starts)
    closer = "}" if text[first] == "{" else "]"
    last = text.rfind(closer)
    if last < first:
        raise ValueError(f"JSON block never closes in model text: {text[:200]!r}")
    try:
        return json.loads(text[first:last + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"model text is not valid JSON ({e.msg}): {text[first:first + 200]!r}") from e
