"""Build retrieval context, call LLM, parse citations."""

from __future__ import annotations

import re

from .llm import generate_ex, is_no_answer
from .retrieval import RetrievedTicket

_CITE_RE = re.compile(r"\[(\d+)\]")


def build_context(hits: list[RetrievedTicket]) -> str:
    blocks = []
    for h in hits:
        blocks.append(
            f"[{h.ticket_id}] (similarity {h.similarity:.2f})\n"
            f"Q: {(h.text or h.snippet)[:700]}\n"
            f"A: {h.answer[:800]}"
        )
    return "\n\n".join(blocks)


def answer_from_hits_ex(question: str, hits: list[RetrievedTicket]) -> tuple[str | None, list[int], str | None]:
    """
    Returns (answer_or_None, cited_ticket_ids, method).
    None answer means treat as no-match → escalate. method names the model that wrote the answer, or is None
    when no model answered and the closest past answer is reused verbatim.
    """
    if not hits:
        return None, [], None

    context = build_context(hits)
    fallback = hits[0].answer
    raw, method = generate_ex(question, context, fallback_answer=fallback)

    if is_no_answer(raw):
        return None, [], method

    cited = [int(x) for x in _CITE_RE.findall(raw)]
    if not cited:
        # If model didn't cite, attach top hit as implicit source
        cited = [hits[0].ticket_id]
    return raw, cited, method


def answer_from_hits(question: str, hits: list[RetrievedTicket]) -> tuple[str | None, list[int]]:
    """(answer_or_None, cited_ticket_ids). See answer_from_hits_ex."""
    answer, cited, _ = answer_from_hits_ex(question, hits)
    return answer, cited
