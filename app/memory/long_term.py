"""Long-term memory: a sqlite table of ManagerDecision, one row per thread and question.

Does: save_decision (idempotent on thread_id plus question), list_decisions, recall by BM25 over past questions.
Does not: feed prompts directly. The graph turns recalled decisions into a data block. Nothing here becomes a citation.
"""
import sqlite3
from datetime import datetime

from rank_bm25 import BM25Okapi

from app import config
from app.contract import ManagerDecision
from app.ingest.index import tokenize

TABLE = ("CREATE TABLE IF NOT EXISTS manager_decisions ("
         "thread_id TEXT NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL, reason TEXT NOT NULL, "
         "decided_by TEXT NOT NULL, decided_at TEXT NOT NULL, PRIMARY KEY (thread_id, question))")


def connect() -> sqlite3.Connection:
    """Open the memory db, creating the folder and table if this is the first run."""
    config.MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.MEMORY_DB), timeout=10)
    conn.execute(TABLE)
    return conn


def save_decision(decision: ManagerDecision) -> None:
    """Write one decision. The same thread and question twice keeps the first row, so a retry cannot double-write."""
    conn = connect()
    with conn:
        conn.execute("INSERT OR IGNORE INTO manager_decisions VALUES (?, ?, ?, ?, ?, ?)",
                     (decision.thread_id, decision.question, decision.answer, decision.reason,
                      decision.decided_by, decision.decided_at.isoformat()))
    conn.close()


def list_decisions() -> list[ManagerDecision]:
    """Every decision, newest first. Empty list when nothing has been decided yet."""
    conn = connect()
    rows = conn.execute("SELECT thread_id, question, answer, reason, decided_by, decided_at "
                        "FROM manager_decisions ORDER BY decided_at DESC").fetchall()
    conn.close()
    return [ManagerDecision(thread_id=r[0], question=r[1], answer=r[2], reason=r[3], decided_by=r[4],
                            decided_at=datetime.fromisoformat(r[5])) for r in rows]


def recall(question: str) -> list[ManagerDecision]:
    """Top MEMORY_MAX_ITEMS past decisions ordered by BM25 over their questions. A decision must share a word with
    the question to count; BM25's own score goes negative on a one or two row table, so it orders but does not gate."""
    decisions = list_decisions()
    if not decisions:
        return []
    asked = set(tokenize(question))
    scores = BM25Okapi([tokenize(d.question) for d in decisions]).get_scores(tokenize(question))
    ranked = sorted(range(len(decisions)), key=lambda n: -scores[n])
    # no shared word means no match, whatever BM25 says
    matched = [decisions[n] for n in ranked if asked & set(tokenize(decisions[n].question))]
    return matched[:config.MEMORY_MAX_ITEMS]
