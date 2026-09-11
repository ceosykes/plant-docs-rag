"""The five objects that cross a boundary. Everything codes to these names verbatim.

Does: define the shapes the graph, the API, the eval and the front end all share.
Does not: hold logic. No defaults that hide a missing field.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Corpus = Literal["safety", "maintenance", "quality"]
Status = Literal["answered", "refused", "waiting_for_manager", "answered_by_manager"]


class Question(BaseModel):
    """What the floor supervisor typed, on which thread."""
    thread_id: str
    text: str = Field(min_length=1)
    asked_at: datetime


class Finding(BaseModel):
    """One verbatim quote a specialist pulled from one chunk. The unit of citation."""
    corpus: Corpus
    quote: str = Field(min_length=1)
    source: str            # file name, e.g. osha3120_lockout_tagout.pdf
    title: str             # human title from the manifest
    locator: str           # "page 12" for PDFs; "section 3.2" or "slide 4" for others
    doc_date: str          # as printed on the document, e.g. "2002 (Revised)"
    why_it_matters: str    # the specialist's one line on why this quote answers the question
    source_url: str = ""   # the publisher's copy, from the manifest, so a person can open the real thing
    verified: bool = False # set in code only, true when quote is a substring of the chunk


class SpecialistReport(BaseModel):
    """What one specialist sends back to customer service. Never a raw chunk."""
    corpus: Corpus
    findings: list[Finding]
    refused: bool          # true when the specialist emitted the refusal string
    reasoning: str         # the specialist's own account of what it looked for and found
    chunks_seen: int       # how many chunks retrieval handed it


class Answer(BaseModel):
    """What the supervisor reads, plus everything the 'why this answer' panel shows."""
    thread_id: str
    status: Status
    text: str
    corpora_chosen: list[Corpus]
    router_reason: str
    reports: list[SpecialistReport]
    memory_used: list[str]  # past manager decisions fed in as context, as plain strings
    steps_ran: list[str]    # node names in the order they ran
    answered_at: datetime


class ManagerDecision(BaseModel):
    """A person's answer to an escalated question, with the reason. This is long-term memory."""
    thread_id: str
    question: str
    answer: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    decided_by: str
    decided_at: datetime
