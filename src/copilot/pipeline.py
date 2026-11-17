"""Main ask(question) → AskResponse pipeline."""

from __future__ import annotations

import time

from .config import SIM_THRESHOLD, TOP_K
from .escalation import create_escalation
from .feedback import log_interaction
from .intent import predict_intent
from .llm import expand_query, last_error, provider_name
from .rag import answer_from_hits_ex
from .retrieval import search
from .schemas import AskResponse, SourceTicket
from .severity import predict_severity

# Questions up to this many words are also searched in a ticket-style rewording (needs a language model).
EXPAND_MAX_WORDS = 25


def ask(question: str, *, log: bool = True, escalate: bool = True, requester: str | None = None) -> AskResponse:
    """Answer from the ticket knowledge base or escalate. With escalate=False an unanswerable question
    returns route "unanswered" instead of creating an escalation (used for questions too short to match)."""
    t0 = time.perf_counter()
    q = (question or "").strip()
    if not q:
        return AskResponse(
            route="escalated",
            intent="Request",
            answer="Please enter a non-empty question.",
            confidence=0.0,
            latency_ms=0,
        )

    # 1) Intent
    try:
        intent = predict_intent(q)
    except FileNotFoundError:
        intent = "Request"

    # 2) Semantic search. A short message ("I forgot my password") scores low against long ticket texts even
    #    when it is the same problem, so with a language model configured it is also searched in a fuller,
    #    ticket-style wording. Each ticket keeps its best score; the threshold and the grounded check below
    #    are unchanged, so this cannot make an unrelated ticket pass.
    search_text = expand_query(q) if provider_name() and len(q.split()) <= EXPAND_MAX_WORDS else None
    hits = search(q, k=TOP_K, also=[search_text] if search_text else None)
    top_sim = hits[0].similarity if hits else 0.0
    sources = [
        SourceTicket(ticket_id=h.ticket_id, similarity=round(h.similarity, 4), snippet=h.snippet)
        for h in hits
    ]

    # 3) Confidence check → RAG or escalate
    method = None
    if hits and top_sim >= SIM_THRESHOLD:
        answer, _cited, method = answer_from_hits_ex(q, hits)
        if answer is not None:
            resp = AskResponse(
                route="resolved",
                intent=intent,
                answer=answer,
                sources=sources,
                confidence=round(top_sim, 4),
                severity=None,
                escalation_id=None,
                latency_ms=int((time.perf_counter() - t0) * 1000),
                method=method,
                search_text=search_text,
                llm_error=None if method else last_error(),
            )
            if log:
                log_interaction(q, resp)
            return resp
        # LLM said NO_ANSWER → fall through to escalate

    if not escalate:
        return AskResponse(route="unanswered", intent=intent, answer=None, sources=sources,
                           confidence=round(top_sim, 4), latency_ms=int((time.perf_counter() - t0) * 1000),
                           search_text=search_text, llm_error=last_error())

    # 4) Severity + escalation
    try:
        severity = predict_severity(q)
    except FileNotFoundError:
        from .schemas import SeverityInfo

        severity = SeverityInfo(label="medium", score=0.5, top_terms=[])

    neighbors = [
        {
            "ticket_id": h.ticket_id,
            "similarity": round(h.similarity, 4),
            "snippet": h.snippet,
            "answer": h.answer[:400],
        }
        for h in hits
    ]
    esc_id = create_escalation(q, intent, severity, neighbors, requester=requester)

    resp = AskResponse(
        route="escalated",
        intent=intent,
        answer=None,
        sources=sources,
        confidence=round(top_sim, 4),
        severity=severity,
        escalation_id=esc_id,
        latency_ms=int((time.perf_counter() - t0) * 1000),
        search_text=search_text,
        llm_error=last_error(),
    )
    if log:
        log_interaction(q, resp)
    return resp
