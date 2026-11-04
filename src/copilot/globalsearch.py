"""One search box across tickets, documents, tasks and the historical ticket archive."""

from __future__ import annotations

from .db import fetchall
from .preprocess import enough_keywords, matched_keywords, search_keywords


def _word_search(table: str, columns: list[str], select: str, words: list[str], phrase: str, limit: int) -> list[dict]:
    """Rows containing any of the words (or the whole phrase), most words matched first."""
    terms = words or [phrase.lower()]
    where = " OR ".join("(" + " OR ".join(f"LOWER(COALESCE({c}, '')) LIKE ?" for c in columns) + ")" for _ in terms)
    params = [f"%{t}%" for t in terms for _ in columns]
    concat = " || ' ' || ".join(f"COALESCE({c}, '')" for c in columns)
    rows = fetchall(f"SELECT {select}, {concat} AS _text FROM {table} WHERE {where} ORDER BY id DESC LIMIT 100",
                    tuple(params))
    for r in rows:
        text = r.pop("_text") or ""
        r["matched_words"] = matched_keywords(words, text) if words else ([phrase] if phrase.lower() in text.lower() else [])
    rows = [r for r in rows if (enough_keywords(r["matched_words"], words) if words else r["matched_words"])]
    rows.sort(key=lambda r: (-len(r["matched_words"]), -r["id"]))
    return rows[:limit]


def search_all(q: str, limit: int = 8, actor: dict | None = None) -> dict:
    """Search everything the actor may see. Employees get their own tickets (raised by them or
    assigned to them), documents and the archive; tasks are Senior Analyst work and are left out."""
    q = (q or "").strip()
    out = {"tickets": [], "documents": [], "doc_passages": [], "tasks": [], "archive": [], "errors": []}
    if not q:
        return out
    words = search_keywords(q)
    try:
        from .triage import search_tickets, search_tickets_for

        out["tickets"] = search_tickets_for(q, actor, k=limit) if actor else search_tickets(q, k=limit)
    except Exception as e:
        out["errors"].append(f"Ticket search unavailable: {e}")
    if not actor or actor.get("role") == "analyst":
        out["tasks"] = _word_search("tasks", ["title", "description", "assignee"],
                                    "id, title, status, priority, due_at", words, q, limit)
    out["documents"] = _word_search("documents", ["title", "filename", "tags", "collection"],
                                    "id, title, collection, file_type", words, q, limit)
    try:
        from .knowledge import search_documents

        out["doc_passages"] = [h for h in search_documents(q, k=5) if h["similarity"] >= 0.3]
    except Exception as e:
        out["errors"].append(f"Document search unavailable: {e}")
    try:
        from .retrieval import search

        out["archive"] = [
            {"ticket_id": h.ticket_id, "similarity": h.similarity, "snippet": h.snippet,
             "priority": h.metadata.get("priority"), "source": h.metadata.get("source")}
            for h in search(q, k=5)
        ]
    except Exception as e:
        out["errors"].append(f"Archive search unavailable: {e}")
    return out
