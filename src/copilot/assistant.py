"""AI Assistant: the company's conversational assistant (talks like ChatGPT or Gemini, but only about work here).
It knows the company's uploaded documents and how past support tickets were solved, and politely declines topics
unrelated to work.

The language model writes every reply, with the conversation so far and the related documents and past cases as
background. Without a working model the assistant says so and shows the closest real passage or past answer;
nothing is made up. Match scores and escalation to a Senior Analyst live in Find a fix, not in the chat.
"""

from __future__ import annotations

import json
import re

from .config import DOC_SIM_THRESHOLD, SIM_THRESHOLD
from .db import execute, fetchall

_SUMMARY_RE = re.compile(r"^\s*(summari[sz]e|summary of|give me a summary of|tl;?dr)\b[:\s]*(.*)$", re.I)
_TICKET_OVERVIEW_RE = re.compile(r"\b(ticket|tickets)\b", re.I)


def save_message(user_email: str, role: str, content: str, meta: dict | None = None) -> int:
    return execute(
        "INSERT INTO chat_messages (user_email, role, content, meta_json) VALUES (?, ?, ?, ?)",
        (user_email, role, content, json.dumps(meta or {})),
    )


def history(user_email: str, limit: int = 60) -> list[dict]:
    rows = fetchall(
        "SELECT * FROM (SELECT * FROM chat_messages WHERE user_email = ? ORDER BY id DESC LIMIT ?) ORDER BY id",
        (user_email, limit),
    )
    for r in rows:
        r["meta"] = json.loads(r.get("meta_json") or "{}")
    return rows


def clear_history(user_email: str) -> None:
    execute("DELETE FROM chat_messages WHERE user_email = ?", (user_email,))


def _best_paragraph(question: str, text: str) -> str:
    """Within a retrieved chunk, the paragraph closest to the question (same embedding model)."""
    from .retrieval import embed_texts

    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) > 40]
    if len(paras) <= 1:
        return text
    q, *ps = embed_texts([question] + paras)
    scores = [sum(a * b for a, b in zip(q, p)) for p in ps]
    return paras[max(range(len(paras)), key=lambda i: scores[i])]


def _log(question: str, intent: str, answer: str, confidence: float, latency_ms: int) -> int:
    return execute(
        "INSERT INTO interactions (question, route, intent, confidence, answer, latency_ms) VALUES (?, 'resolved', ?, ?, ?, ?)",
        (question, intent, confidence, answer, latency_ms),
    )


def _ticket_overview(days: int = 7) -> dict:
    """Real numbers from the ticket store, phrased as a short summary."""
    from .triage import ticket_stats

    rows = fetchall(
        "SELECT COALESCE(final_priority, predicted_priority) AS p, status, COUNT(*) AS n FROM tickets "
        "WHERE source != 'archive' AND created_at >= datetime('now', ?) GROUP BY p, status",
        (f"-{days} days",),
    )
    if not rows:
        return {"kind": "overview", "text": f"No tickets were triaged in the last {days} days. "
                "Submit one on the Smart Triage page and I can summarize the queue."}
    total = sum(r["n"] for r in rows)
    by_p = {p: sum(r["n"] for r in rows if r["p"] == p) for p in ("high", "medium", "low")}
    open_n = sum(r["n"] for r in rows if r["status"] in ("open", "in_progress"))
    s = ticket_stats(include_archive=False)
    recent_high = fetchall(
        "SELECT id, subject FROM tickets WHERE source != 'archive' AND status IN ('open','in_progress') "
        "AND COALESCE(final_priority, predicted_priority) = 'high' ORDER BY id DESC LIMIT 3"
    )
    lines = [
        f"In the last {days} days, {total} ticket{'s' if total != 1 else ''} were triaged: "
        f"{by_p['high']} high, {by_p['medium']} medium and {by_p['low']} low priority. "
        f"{open_n} of them are still open.",
    ]
    if s["agreement_pct"] is not None:
        lines.append(f"Agents kept the model's priority on {s['agreement_pct']:.0f}% of tickets "
                     f"({s['corrected']} corrected).")
    if recent_high:
        lines.append("Open high-priority tickets: " + "; ".join(f"#{r['id']} {r['subject'][:60]}" for r in recent_high) + ".")
    return {"kind": "overview", "text": " ".join(lines)}


def _summarize_request(target: str) -> dict:
    from .knowledge import list_documents, search_documents, summarize

    target = target.strip().strip('"“”.')
    docs = list_documents()
    if target and _TICKET_OVERVIEW_RE.search(target) and not any(target.lower() in d["title"].lower() for d in docs):
        return _ticket_overview()
    if not docs:
        return {"kind": "info", "text": "There are no documents to summarize yet. Upload one in the Knowledge Hub."}
    doc = None
    if target:
        exact = [d for d in docs if target.lower() in d["title"].lower() or target.lower() in d["filename"].lower()]
        if exact:
            doc = exact[0]
        else:
            hits = search_documents(target, k=1)
            if hits:
                doc = next((d for d in docs if d["id"] == hits[0]["doc_id"]), None)
    if doc is None:
        titles = ", ".join(f"“{d['title']}”" for d in docs[:5])
        return {"kind": "info", "text": f"Which document should I summarize? Try: summarize {titles}."}
    s = summarize(doc["id"])
    return {"kind": "summary", "doc_id": doc["id"], "title": doc["title"], **s}


_SYSTEM_PROMPT = """You are PRAGYAAN, the AI assistant of this company, for its employees. Talk naturally and warmly, the way
ChatGPT or Gemini do: answer directly, explain clearly, use short paragraphs, and numbered steps or bullet points when
they help. If a request is unclear, ask a short follow-up question.

You only help with work at this company:
- the company's policies, processes, tools and documents ("how does X work here?"), and summarizing them;
- IT, HR, access, account, device, software and other workplace problems, and explaining fixes step by step;
- writing work emails, messages or requests (to IT, HR, a manager, a colleague or a customer);
- explaining work and technical concepts an employee needs for their job.

If the message is not about work (for example recipes, films, sports, games, travel plans, relationships, school
homework, general trivia or jokes), do not answer it. Say in one or two friendly sentences that you are the company's
work assistant and can only help with work, and give one example of what you can help with. Greetings and thanks are
fine: reply briefly and say what you can help with.

{context}

Rules:
- For facts specific to this company (its policies, contacts, internal tools, deadlines, numbers, procedures), rely
  only on the company material above. If it doesn't cover it, say you don't have that information and suggest
  raising a ticket from the Home page so the support team can help.
- When a company document helps, mention its title naturally, e.g. "According to the VPN policy, ...".
- The past support cases show how similar problems were handled; use them as hints for troubleshooting, but
  never copy their greetings, placeholders or requests for account numbers.
- Never mention similarity scores, retrieval, "the context" or "the provided documents" as such.
- Never claim to be ChatGPT, Gemini or any other product. You are PRAGYAAN, the company's assistant."""

_HELP = ("Hi! I'm PRAGYAAN, your company's work assistant. Ask me how something works here, get help with an IT or "
         "HR problem, or let me draft a work email. Type “summarize” and a document name to get its key points.")


def _prior_turns(prior: list[dict], limit: int = 8) -> list[dict]:
    """The recent conversation as chat messages (skips empty or system-like entries)."""
    turns = []
    for m in prior[-limit:]:
        text = (m.get("content") or "").strip()
        if not text:
            continue
        turns.append({"role": "user" if m["role"] == "user" else "assistant", "content": text[:1500]})
    return turns


def _gather_context(q: str, prior: list[dict]) -> dict:
    """Company documents and past support cases related to the message (follow-ups also use the previous
    question, so "it still drops" finds the VPN material)."""
    from .knowledge import search_documents
    from .retrieval import search

    query = q
    if len(q.split()) < 8:
        prev = next((m["content"] for m in reversed(prior) if m["role"] == "user" and m.get("content")), "")
        if prev:
            query = f"{prev} {q}"
    try:
        docs = [h for h in search_documents(query, k=4) if h["similarity"] >= DOC_SIM_THRESHOLD - 0.1][:3]
    except Exception:
        docs = []
    try:
        tickets = [h for h in search(query, k=4) if h.similarity >= SIM_THRESHOLD - 0.05 and (h.answer or "").strip()][:3]
    except Exception:
        tickets = []
    return {"docs": docs, "tickets": tickets}


def _context_block(ctx: dict) -> str:
    parts = []
    if ctx.get("focus"):
        parts.append(f"THE FIX THE EMPLOYEE IS ASKING ABOUT (from {ctx['focus']['source']}). Explain how to apply it "
                     f"to their problem, step by step:\n{ctx['focus']['text']}")
    if ctx["docs"]:
        parts.append("COMPANY DOCUMENTS:\n" + "\n\n".join(
            f"[{h['title']}]\n{h['text'][:1800]}" for h in ctx["docs"]))
    if ctx["tickets"]:
        parts.append("PAST SUPPORT CASES (problem, then how support replied):\n" + "\n\n".join(
            f"Problem: {(h.text or h.snippet)[:500]}\nReply: {h.answer[:600]}" for h in ctx["tickets"]))
    return "\n\n".join(parts) if parts else "No company documents or past support cases relate to this message."


def _fallback(q: str, ctx: dict, err: str | None) -> tuple[str, str]:
    """Without a working language model: say so honestly, and show the closest real material if there is any.
    Returns (text, what it is)."""
    from .explain import is_small_talk

    why = (f"I can't reach the language model right now ({err})" if err else
           "No language model is connected (add GROQ_API_KEY to .env)")
    if is_small_talk(q):
        return _HELP, "help"
    if ctx.get("focus"):
        return f"{why}, so here is {ctx['focus']['source']} as it was written:\n\n{ctx['focus']['text']}", "focus"
    if ctx["docs"] and ctx["docs"][0]["similarity"] >= DOC_SIM_THRESHOLD:
        top = ctx["docs"][0]
        return (f"{why}, so here is the most relevant part of **{top['title']}**:\n\n"
                f"{_best_paragraph(q, top['text'])}"), "document"
    if ctx["tickets"] and ctx["tickets"][0].similarity >= SIM_THRESHOLD:
        return (f"{why}, so here is how support answered a very similar problem:\n\n"
                f"{ctx['tickets'][0].answer}"), "ticket"
    return (f"{why}, so I can't write an answer. For known problems, try **Find a fix** on your Home page; it "
            "searches solved tickets and your company's documents without the language model."), "none"


def answer_stream(question: str, user_email: str | None = None, out: dict | None = None, *,
                  focus: dict | None = None):
    """Reply to a chat message, yielding the text as it is written. `out` receives the stored message metadata.

    The reply is written by the language model with the conversation so far and related company documents and
    past support cases as background. "summarize <document>" and a ticket overview still work as commands.
    Nothing is escalated from here; known-fix search with match scores and escalation live in Find a fix.
    `focus` ({"source", "text"}) is a fix opened from Find a fix ("Explain this step by step").
    """
    import time

    from .llm import chat_stream, last_error, last_model, provider_name

    out = {} if out is None else out
    t0 = time.perf_counter()
    q = (question or "").strip()
    if not q:
        out.update(kind="info", text="Type a question first.")
        yield out["text"]
        return
    prior = history(user_email, limit=12) if user_email else []
    if user_email:
        save_message(user_email, "user", q)
    try:
        from .intent import predict_intent

        intent = predict_intent(q)
    except Exception:
        intent = "Request"

    m = _SUMMARY_RE.match(q)
    if m or (re.search(r"\b(overview|summary|summari[sz]e)\b", q, re.I) and _TICKET_OVERVIEW_RE.search(q)):
        res = _summarize_request(m.group(2)) if m else _ticket_overview()
        out.update(res)
        if res.get("kind") == "summary":
            yield res.get("summary") or "\n".join(f"- {s}" for s in res.get("sentences") or []) or \
                "The document is too short to summarize."
        else:
            yield res.get("text") or ""
    else:
        ctx = _gather_context(q, prior)
        if focus and (focus.get("text") or "").strip():
            ctx["focus"] = {"source": str(focus.get("source") or "Find a fix")[:120], "text": str(focus["text"])[:2500]}
        messages = ([{"role": "system", "content": _SYSTEM_PROMPT.format(context=_context_block(ctx))}]
                    + _prior_turns(prior) + [{"role": "user", "content": q}])
        parts: list[str] = []
        if provider_name():
            for chunk in chat_stream(messages):
                parts.append(chunk)
                yield chunk
        text, err = "".join(parts).strip(), last_error()
        method, used = (last_model() if text else None), "model"
        if not text:
            text, used = _fallback(q, ctx, err)
            yield text
        elif err:
            note = f"\n\n_(The reply was cut off: {err}.)_"
            text += note
            yield note
        out.update(
            kind="ai", text=text, method=method, used=used, intent=intent,
            llm_error=None if method and not err else err,
            doc_sources=[{"doc_id": h["doc_id"], "title": h["title"], "collection": h.get("collection"),
                          "similarity": h["similarity"], "text": h["text"][:600]} for h in ctx["docs"]],
            sources=[{"ticket_id": h.ticket_id, "similarity": round(h.similarity, 4), "snippet": h.snippet}
                     for h in ctx["tickets"]],
            # the message looks like a support problem that solved tickets cover: offer Find a fix (not when the
            # employee came from Find a fix already)
            find_fix=bool(ctx["tickets"]) and not ctx.get("focus") and used == "model",
            focus_source=(ctx.get("focus") or {}).get("source"),
        )
        best = max([h["similarity"] for h in ctx["docs"]] + [h.similarity for h in ctx["tickets"]] + [0.0])
        out["interaction_id"] = _log(q, intent, text, round(best, 4), int((time.perf_counter() - t0) * 1000))
    out["question"] = q
    out["latency_ms"] = out.get("latency_ms") or int((time.perf_counter() - t0) * 1000)
    if user_email:
        out["message_id"] = save_message(user_email, "assistant", out.get("text") or "", out)


def answer(question: str, user_email: str | None = None, *, focus: dict | None = None) -> dict:
    """Reply to a chat message without streaming. Returns the stored message metadata (text, sources ...)."""
    out: dict = {}
    for _ in answer_stream(question, user_email, out, focus=focus):
        pass
    return out


def rate_answer(message_id: int, user_email: str, thumbs: str) -> None:
    """Thumbs up / down on one of the user's own assistant replies (feeds the helpfulness numbers)."""
    from .feedback import set_thumbs

    msg, meta = _own_answer(message_id, user_email)
    if meta.get("interaction_id"):
        set_thumbs(int(meta["interaction_id"]), thumbs)
    meta["thumbs"] = thumbs
    execute("UPDATE chat_messages SET meta_json = ? WHERE id = ?", (json.dumps(meta), msg["id"]))


def escalate_question(question: str, user_email: str, *, best_similarity: float = 0.0, neighbors: list | None = None,
                      note: str | None = None) -> dict:
    """Find a fix found nothing that helped: the employee sends the question to the Senior Queue. Their answer
    comes back as a notification and into the assistant chat. Returns the escalation id and its explanation."""
    from .activity import log_activity, notify
    from .escalation import create_escalation
    from .explain import explain_escalation
    from .schemas import SeverityInfo

    q = (question or "").strip()
    if not q:
        raise ValueError("Describe the problem first.")
    try:
        from .severity import predict_severity

        severity = predict_severity(f"{q}. {note or ''}".strip(". "))
    except FileNotFoundError:
        severity = SeverityInfo(label="medium", score=0.5, top_terms=[])
    try:
        from .intent import predict_intent

        intent = predict_intent(q)
    except Exception:
        intent = "Request"
    esc_id = create_escalation(q, intent, severity, neighbors or [], requester=user_email,
                               source="not_resolved" if neighbors else "unanswered", note=note)
    execute("INSERT INTO interactions (question, route, intent, confidence, severity_label, severity_score, "
            "escalation_id) VALUES (?, 'escalated', ?, ?, ?, ?, ?)",
            (q, intent, round(float(best_similarity or 0), 4), severity.label, severity.score, esc_id))
    log_activity("escalation", f"Find a fix found no answer; question escalated to the senior queue (#{esc_id})",
                 ref_type="escalation", ref_id=esc_id, actor=user_email)
    notify(f"New question in the senior queue (#{esc_id}): “{q[:60]}”", level="info", page="queue", ref_id=esc_id)
    return {"escalation_id": esc_id, "severity": severity.model_dump(),
            "explain": explain_escalation(q, best_similarity, severity.model_dump())}


def _own_answer(message_id: int, user_email: str) -> tuple[dict, dict]:
    """The assistant message `message_id`, only if it belongs to `user_email` (nobody can act on another
    person's chat), with its metadata."""
    row = fetchall("SELECT * FROM chat_messages WHERE id = ? AND user_email = ? AND role = 'assistant'",
                   (int(message_id), user_email))
    if not row:
        raise ValueError("That answer isn't in your conversation.")
    msg = row[0]
    return msg, json.loads(msg.get("meta_json") or "{}")


def _question_for(msg: dict, meta: dict, user_email: str) -> str:
    if meta.get("question"):
        return meta["question"]
    prev = fetchall("SELECT content FROM chat_messages WHERE user_email = ? AND role = 'user' AND id < ? "
                    "ORDER BY id DESC LIMIT 1", (user_email, msg["id"]))
    return prev[0]["content"] if prev else ""


def mark_answer_resolved(message_id: int, user_email: str) -> None:
    """The employee says the answer solved it: recorded as helpful."""
    from .feedback import set_thumbs

    msg, meta = _own_answer(message_id, user_email)
    if meta.get("interaction_id"):
        set_thumbs(int(meta["interaction_id"]), "up")
    meta["feedback"] = "resolved"
    execute("UPDATE chat_messages SET meta_json = ? WHERE id = ?", (json.dumps(meta), msg["id"]))


def escalate_answer(message_id: int, user_email: str, note: str | None = None) -> int:
    """The employee says the answer didn't solve it: the question goes to the Senior Queue with the answer
    they were given and their note. The senior's reply comes back into their chat. Returns the escalation id."""
    from .activity import log_activity, notify
    from .escalation import create_escalation
    from .feedback import set_thumbs
    from .schemas import SeverityInfo
    from .severity import predict_severity

    msg, meta = _own_answer(message_id, user_email)
    if meta.get("escalated_id"):
        return int(meta["escalated_id"])
    if meta.get("kind") not in ("documents", "resolved", "ai"):
        raise ValueError("Only answers can be escalated.")
    q = _question_for(msg, meta, user_email)
    try:
        severity = predict_severity(f"{q}. {note or ''}".strip(". "))
    except FileNotFoundError:
        severity = SeverityInfo(label="medium", score=0.5, top_terms=[])
    neighbors = [{"ticket_id": s.get("ticket_id"), "similarity": s.get("similarity"), "snippet": s.get("snippet"),
                  "answer": ""} for s in meta.get("sources") or []]
    neighbors += [{"ticket_id": f"doc {d.get('doc_id')}", "similarity": d.get("similarity"),
                   "snippet": f"{d.get('title')}: {(d.get('text') or '')[:200]}", "answer": ""}
                  for d in meta.get("doc_sources") or []]
    esc_id = create_escalation(q, meta.get("intent") or "Request", severity, neighbors, requester=user_email,
                               source="not_resolved", attempted_answer=msg.get("content") or "", note=note)
    if meta.get("interaction_id"):
        set_thumbs(int(meta["interaction_id"]), "down")
    meta["escalated_id"], meta["feedback"] = esc_id, "not_resolved"
    execute("UPDATE chat_messages SET meta_json = ? WHERE id = ?", (json.dumps(meta), msg["id"]))
    log_activity("escalation", f"Assistant answer didn't solve it; question escalated to the senior queue (#{esc_id})",
                 ref_type="escalation", ref_id=esc_id, actor=user_email)
    notify(f"An employee says the assistant's answer didn't help (#{esc_id}): “{q[:60]}”", level="info",
           page="queue", ref_id=esc_id)
    return esc_id


__all__ = ["answer", "answer_stream", "history", "clear_history", "save_message", "rate_answer",
           "mark_answer_resolved", "escalate_answer", "escalate_question", "SIM_THRESHOLD", "DOC_SIM_THRESHOLD"]
