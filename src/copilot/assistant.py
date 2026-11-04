"""AI Assistant: answers from uploaded documents, then the ticket knowledge base,
otherwise escalates to the senior queue (the existing closed loop).

Without an LLM key every answer is retrieved text (a passage or a past ticket's
answer) with its source; nothing is generated or guessed.
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


def answer(question: str, user_email: str | None = None) -> dict:
    """Route a question. Returns a dict the UI renders; also persisted when user_email is given."""
    import time

    from .intent import predict_intent
    from .knowledge import search_documents
    from .llm import complete, is_no_answer, provider_name
    from .pipeline import ask

    t0 = time.perf_counter()
    q = (question or "").strip()
    if not q:
        return {"kind": "info", "text": "Type a question first."}
    if user_email:
        save_message(user_email, "user", q)

    m = _SUMMARY_RE.match(q)
    if m:
        out = _summarize_request(m.group(2))
    elif re.search(r"\b(overview|summary|summari[sz]e)\b", q, re.I) and _TICKET_OVERVIEW_RE.search(q):
        out = _ticket_overview()
    else:
        out = None
        try:
            doc_hits = search_documents(q, k=4)
        except Exception:
            doc_hits = []
        try:
            intent = predict_intent(q)
        except FileNotFoundError:
            intent = "Request"
        if doc_hits and doc_hits[0]["similarity"] >= DOC_SIM_THRESHOLD:
            top = [h for h in doc_hits if h["similarity"] >= DOC_SIM_THRESHOLD - 0.1][:3]
            text, method = None, "retrieval"
            if provider_name():
                ctx = "\n\n".join(f"[D{i + 1}] {h['title']}:\n{h['text']}" for i, h in enumerate(top))
                raw = complete(
                    "Answer the employee's question using ONLY the document passages below. "
                    "If they do not contain the answer, reply exactly: NO_ANSWER. Cite passages as [D1], [D2].\n\n"
                    f"PASSAGES:\n{ctx}\n\nQUESTION: {q}"
                )
                if raw and not is_no_answer(raw):
                    text, method = raw, provider_name()
            if text is None and not provider_name():
                text = _best_paragraph(q, top[0]["text"])
            if text is not None:
                out = {
                    "kind": "documents", "text": text, "method": method, "intent": intent,
                    "confidence": doc_hits[0]["similarity"], "doc_sources": top,
                }
                out["interaction_id"] = _log(q, intent, text, doc_hits[0]["similarity"],
                                             int((time.perf_counter() - t0) * 1000))
        if out is None:
            resp = ask(q)
            out = {"kind": resp.route, "text": resp.answer or "", "intent": resp.intent,
                   "confidence": resp.confidence, "latency_ms": resp.latency_ms,
                   "sources": [s.model_dump() for s in resp.sources],
                   "severity": resp.severity.model_dump() if resp.severity else None,
                   "escalation_id": resp.escalation_id,
                   "method": provider_name() or "retrieval",
                   "related_docs": [h for h in doc_hits[:2] if h["similarity"] >= 0.3]}
            last = fetchall("SELECT id FROM interactions ORDER BY id DESC LIMIT 1")
            out["interaction_id"] = last[0]["id"] if last else None
            if resp.route == "escalated":
                from .activity import log_activity, notify

                log_activity("escalation", f"Question escalated to the senior queue (#{resp.escalation_id})",
                             ref_type="escalation", ref_id=resp.escalation_id, actor=user_email)
                notify(f"New question in the senior queue (#{resp.escalation_id})", level="info",
                       page="queue", ref_id=resp.escalation_id)
    out["latency_ms"] = out.get("latency_ms") or int((time.perf_counter() - t0) * 1000)
    if user_email:
        save_message(user_email, "assistant", out.get("text") or "", out)
    return out


__all__ = ["answer", "history", "clear_history", "save_message", "SIM_THRESHOLD", "DOC_SIM_THRESHOLD"]
