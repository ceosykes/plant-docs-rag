"""LLM as judge for one generated answer against the golden answer key.

Does: score correct, grounded and plain_language as 0 or 1 with a one line reason.
Does not: judge unanswerable questions with the model; that is a status check in code.
"""
import json
import os

import anthropic

from app import config

JUDGE_SYSTEM = """You grade one answer from a plant documentation assistant for a floor supervisor.
Return only a JSON object with these keys and nothing else:
  "correct": 1 if the answer states the fact in the answer key (same meaning, numbers must match), else 0
  "grounded": 1 if every factual claim in the answer is supported by one of the quoted findings, else 0
  "plain_language": 1 if a fifth grader could follow the answer, else 0
  "reason": one sentence saying what decided the scores
An answer that refuses or escalates when the key has a real fact is correct 0."""


def judge_prompt(question: str, answer_key: str, answer_text: str, findings: list[dict]) -> str:
    """Lay out the question, the key, the answer and the quotes the answer was written from."""
    quotes = "\n".join(f"- [{f['source']} {f['locator']}] {f['quote']}" for f in findings) or "(no findings)"
    return (f"QUESTION:\n{question}\n\nANSWER KEY:\n{answer_key}\n\n"
            f"SYSTEM ANSWER:\n{answer_text}\n\nQUOTED FINDINGS THE ANSWER WAS WRITTEN FROM:\n{quotes}")


def parse_scores(text: str) -> dict:
    """Pull the JSON object out of the judge's text; raise if it is not the expected shape."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError(f"judge returned no JSON object: {text[:200]!r}")
    scores = json.loads(text[start:end + 1])
    for key in ("correct", "grounded", "plain_language", "reason"):
        if key not in scores:
            raise ValueError(f"judge JSON is missing {key!r}: {scores}")
    return {"correct": int(scores["correct"]), "grounded": int(scores["grounded"]),
            "plain_language": int(scores["plain_language"]), "reason": str(scores["reason"])}


def judge_unanswerable(status: str) -> dict:
    """Code, not a model: an unanswerable question is right only if the system escalated."""
    escalated = status == "waiting_for_manager"
    reason = "escalated to a manager" if escalated else f"answered with status {status!r} instead of escalating"
    return {"correct": int(escalated), "grounded": int(escalated), "plain_language": 1, "reason": reason}


def judge(item: dict, answer: dict) -> dict:
    """Score one golden item against the Answer dict the graph returned."""
    if item["bucket"] == "unanswerable":
        return judge_unanswerable(answer["status"])
    findings = [f for r in answer.get("reports", []) for f in r.get("findings", [])]
    headers = {"anthropic-workspace-id": os.environ["ANTHROPIC_WORKSPACE_ID"]} if os.environ.get("ANTHROPIC_WORKSPACE_ID") else {}
    client = anthropic.Anthropic(timeout=60, default_headers=headers)
    response = client.messages.create(
        model=config.MODEL, max_tokens=800, system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": judge_prompt(item["question"], item["answer_key"], answer["text"], findings)}],
        output_config={"effort": "low"})
    text = "".join(block.text for block in response.content if block.type == "text")
    return parse_scores(text)
