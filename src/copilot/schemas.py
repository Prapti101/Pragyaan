"""Pydantic request/response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SourceTicket(BaseModel):
    ticket_id: int
    similarity: float
    snippet: str


class SeverityInfo(BaseModel):
    label: Literal["low", "medium", "high"]
    score: float
    top_terms: list[str] = Field(default_factory=list)


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    route: Literal["resolved", "escalated", "unanswered"]
    intent: str
    answer: str | None = None
    sources: list[SourceTicket] = Field(default_factory=list)
    confidence: float = 0.0
    severity: SeverityInfo | None = None
    escalation_id: int | None = None
    latency_ms: int = 0
    method: str | None = None  # the model that wrote the answer; None when a past answer is reused verbatim
    search_text: str | None = None  # ticket-style rewording also used for the search (short questions)
    llm_error: str | None = None  # why the language model was unavailable, when it was


class FeedbackRequest(BaseModel):
    interaction_id: int
    thumbs: Literal["up", "down"]


class ResolveRequest(BaseModel):
    escalation_id: int
    resolution: str
    resolved_by: str = "senior"
