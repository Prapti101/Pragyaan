"""Smart Ticket Triage: real model predictions, ticket storage, corrections, stats."""

from __future__ import annotations

import json
import random
from functools import lru_cache

import joblib

from .activity import log_activity, notify
from .automation import apply_rules
from .config import CHROMA_DIR, MODELS_DIR, SEVERITY_MODEL_PATH, TFIDF_PATH
from .db import execute, fetchall, fetchone
from .preprocess import build_ticket_text, enough_keywords, matched_keywords, search_keywords

PRIORITIES = ("low", "medium", "high")
STATUSES = ("open", "in_progress", "resolved", "closed")
STATUS_LABELS = {"open": "Open", "in_progress": "In progress", "resolved": "Resolved", "closed": "Closed"}


class TriageUnavailable(RuntimeError):
    """The classifier files are missing or could not be loaded."""


@lru_cache(maxsize=1)
def model_name() -> str:
    try:
        meta = joblib.load(MODELS_DIR / "severity_meta.joblib")
        name = str(meta.get("model_name") or "Severity classifier")
        return name.replace("RandomForest", "Random Forest").replace("LogReg", "Logistic Regression")
    except Exception:
        return "Severity classifier"


def model_status() -> dict:
    """Whether the triage models can run, with a fix-it message if not."""
    missing = [p.name for p in (SEVERITY_MODEL_PATH, TFIDF_PATH) if not p.exists()]
    if missing:
        return {"ok": False, "message": f"Missing model files in models/: {', '.join(missing)}. "
                                         "Run scripts/train_severity.py to create them."}
    return {"ok": True, "message": model_name()}


def predict_ticket(subject: str, body: str, *, with_similar: bool = True) -> dict:
    """Run the trained models on subject + body (same text format used in training)."""
    from .intent import intent_probabilities
    from .severity import predict_severity, routing_bucket, severity_probabilities

    text = build_ticket_text(subject, body)
    if not text.strip():
        raise ValueError("Enter a subject or a description.")
    status = model_status()
    if not status["ok"]:
        raise TriageUnavailable(status["message"])
    try:
        probs = severity_probabilities(text)
        info = predict_severity(text)
    except FileNotFoundError as e:
        raise TriageUnavailable(str(e)) from e

    label = max(probs, key=probs.get)
    result = {
        "priority": label,
        "probabilities": {p: float(probs.get(p, 0.0)) for p in PRIORITIES},
        "confidence": float(probs.get(label, 0.0)),
        "score": float(info.score),
        "bucket": routing_bucket(info.score),
        "top_terms": list(info.top_terms),
        "model_name": model_name(),
        "type": None,
        "type_confidence": None,
        "similar": [],
    }
    try:
        ip = intent_probabilities(text)
        t = max(ip, key=ip.get)
        result["type"], result["type_confidence"] = t, float(ip[t])
    except FileNotFoundError:
        pass
    if with_similar:
        try:
            from .retrieval import search

            for h in search(text, k=3):
                result["similar"].append({
                    "ticket_id": h.ticket_id,
                    "similarity": float(h.similarity),
                    "snippet": h.snippet,
                    "answer": h.answer,
                    "priority": h.metadata.get("priority"),
                    "queue": h.metadata.get("queue"),
                })
        except Exception as e:  # knowledge base unavailable: triage still works
            result["similar_error"] = str(e)
    return result


def best_match(prediction: dict) -> dict | None:
    """The closest resolved ticket from the similarity search, if it is close enough to reuse
    its solution (same threshold the assistant uses to answer instead of escalating)."""
    from .config import SIM_THRESHOLD

    hits = [h for h in (prediction.get("similar") or []) if (h.get("answer") or "").strip()]
    if not hits:
        return None
    top = max(hits, key=lambda h: h["similarity"])
    return top if top["similarity"] >= SIM_THRESHOLD else None


def create_ticket(subject: str, body: str, prediction: dict, *, requester: str | None = None,
                  actor: str | None = None, source: str = "manual", status: str = "open",
                  reference_priority: str | None = None, run_automation: bool = True,
                  final_priority: str | None = None, requester_account_id: int | None = None) -> dict:
    """Store a triaged ticket. `final_priority` records an agent override made before saving;
    notifications and automation then follow the final priority.

    Workflow: if the similarity engine found a resolved ticket at or above the match threshold,
    its solution is recommended straight to the employee (review_status 'suggested'): they close
    the ticket if it works, or escalate it. Otherwise the ticket goes to the Senior Analysts'
    New / Escalated queue (review_status 'none'). Senior Analysts don't approve suggestions."""
    p = prediction["probabilities"]
    effective = final_priority if final_priority in PRIORITIES else prediction["priority"]
    match = best_match(prediction) if source == "manual" and status == "open" else None
    tid = execute(
        """
        INSERT INTO tickets (subject, body, requester, predicted_priority, prob_low, prob_medium, prob_high,
                             confidence, severity_score, reason_terms, predicted_type, model_name,
                             reference_priority, status, source, created_by, requester_account_id,
                             match_ticket_id, match_similarity, suggested_solution, review_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (subject.strip(), body.strip(), requester, prediction["priority"], p["low"], p["medium"], p["high"],
         prediction["confidence"], prediction["score"], json.dumps(prediction.get("top_terms") or []),
         prediction.get("type"), prediction.get("model_name"), reference_priority, status, source, actor,
         requester_account_id, match["ticket_id"] if match else None, match["similarity"] if match else None,
         match["answer"].strip() if match else None, "suggested" if match else "none"),
    )
    if effective != prediction["priority"]:
        execute("UPDATE tickets SET final_priority = ?, corrected_by = ?, corrected_at = datetime('now') WHERE id = ?",
                (effective, actor, tid))
    if source == "manual":
        note = "" if effective == prediction["priority"] else f" (model said {prediction['priority']})"
        log_activity("ticket", f"Ticket #{tid} triaged as {effective}{note}: {subject.strip()[:80]}",
                     ref_type="ticket", ref_id=tid, actor=actor)
        if match:
            log_activity("ticket", f"Ticket #{tid}: similar resolved ticket #{match['ticket_id']} found "
                         f"({match['similarity']:.0%} match); its solution was recommended to the requester",
                         ref_type="ticket", ref_id=tid, actor=actor)
            if effective == "high":  # FYI only: no approval needed, but analysts should know
                notify(f"High-priority ticket #{tid} (recommended solution sent to the requester): "
                       f"{subject.strip()[:60]}", level="high", page="triage", ref_id=tid)
        else:
            log_activity("ticket", f"Ticket #{tid}: no close match among resolved tickets; escalated to Senior Analysts",
                         ref_type="ticket", ref_id=tid, actor=actor)
            notify(f"{'High-priority t' if effective == 'high' else 'New escalated t'}icket #{tid}: "
                   f"{subject.strip()[:70]}", level="high" if effective == "high" else "info",
                   page="review", ref_id=tid)
    try:  # make the ticket findable by meaning in global search
        index_ticket(tid, subject, body, source)
    except Exception:
        pass
    auto = {"created": [], "suggestions": []}
    if run_automation:
        auto = apply_rules(tid, effective, subject.strip(), actor=actor)
    return {"ticket_id": tid, **auto}


STAGES = {
    "suggested": "Solution suggested",
    "escalated": "Escalated",
    "assigned": "Assigned",
    "in_progress": "In progress",
    "resolved": "Resolved",
    "closed": "Closed",
}

# Queue definitions shared by list_tickets and queue_counts (all use the t. alias)
_QUEUES = {
    # a recommended solution was shown to the employee, who hasn't said yet whether it worked
    "waiting": "t.status = 'open' AND t.review_status IN ('suggested', 'pending') AND t.assignee_account_id IS NULL",
    # no close match, or the employee said the recommendation didn't help, and nobody assigned yet
    "escalated": "t.status = 'open' AND t.review_status IN ('none', 'rejected', 'declined') "
                 "AND t.assignee_account_id IS NULL AND t.source != 'archive'",
    # closed by the employee with a recommended solution (self-service)
    "self_resolved": "t.review_status = 'self_resolved'",
    "assigned": "t.status IN ('open', 'in_progress') AND t.assignee_account_id IS NOT NULL",
    "active": "t.status IN ('open', 'in_progress')",
}

_SELECT = """
SELECT t.*, ra.name AS requester_name, ra.login_id AS requester_login,
       aa.name AS assignee_name, aa.login_id AS assignee_login
FROM tickets t
LEFT JOIN accounts ra ON ra.id = t.requester_account_id
LEFT JOIN accounts aa ON aa.id = t.assignee_account_id
"""


def _stage(r: dict) -> str:
    if r.get("status") in ("resolved", "closed"):
        return r["status"]
    if r.get("status") == "in_progress":
        return "in_progress"
    if r.get("assignee_account_id"):
        return "assigned"
    if r.get("review_status") in ("suggested", "pending"):
        return "suggested"
    return "escalated"


def _row(r: dict) -> dict:
    r = dict(r)
    r["reason_terms"] = json.loads(r.get("reason_terms") or "[]")
    r["priority"] = r.get("final_priority") or r.get("predicted_priority")
    r["corrected"] = bool(r.get("final_priority")) and r.get("final_priority") != r.get("predicted_priority")
    r["stage"] = _stage(r)
    r["stage_label"] = STAGES[r["stage"]]
    return r


def get_ticket(ticket_id: int) -> dict | None:
    r = fetchone(f"{_SELECT} WHERE t.id = ?", (ticket_id,))
    return _row(r) if r else None


def list_tickets(*, status: str | None = None, priority: str | None = None, q: str | None = None,
                 include_archive: bool = True, limit: int = 500, queue: str | None = None,
                 requester_account_id: int | None = None, assignee_account_id: int | None = None) -> list[dict]:
    where, params = [], []
    if status:
        where.append("t.status = ?")
        params.append(status)
    if priority:
        where.append("COALESCE(t.final_priority, t.predicted_priority) = ?")
        params.append(priority)
    if queue:
        where.append(_QUEUES[queue])
    if requester_account_id is not None:
        where.append("t.requester_account_id = ?")
        params.append(requester_account_id)
    if assignee_account_id is not None:
        where.append("t.assignee_account_id = ?")
        params.append(assignee_account_id)
    words = search_keywords(q) if q else []
    if q:
        terms = ["CAST(t.id AS TEXT) = ?"]
        params.append(q.strip().lstrip("#"))
        for w in words or [q.strip().lower()]:
            terms.append("(LOWER(t.subject) LIKE ? OR LOWER(t.body) LIKE ?)")
            params += [f"%{w}%", f"%{w}%"]
        where.append("(" + " OR ".join(terms) + ")")
    if not include_archive:
        where.append("t.source != 'archive'")
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    rows = [_row(r) for r in fetchall(f"{_SELECT} {clause} ORDER BY t.id DESC LIMIT ?", (*params, limit))]
    if words:  # keep tickets containing enough of the query's words, best matches first
        qid = q.strip().lstrip("#")
        for r in rows:
            r["matched_words"] = matched_keywords(words, f"{r['subject']} {r['body']}")
        rows = [r for r in rows if enough_keywords(r["matched_words"], words) or str(r["id"]) == qid]
        rows.sort(key=lambda r: (-len(r["matched_words"]), -r["id"]))
    return rows


# ---------------------------------------------------------------- search by meaning

_TICKET_INDEX = "my_tickets"


def _ticket_index():
    import chromadb
    from chromadb.config import Settings

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
    return client.get_or_create_collection(name=_TICKET_INDEX, metadata={"hnsw:space": "cosine"})


def _fingerprint(text: str) -> str:
    import hashlib

    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def index_ticket(ticket_id: int, subject: str, body: str, source: str = "manual") -> None:
    """Embed one ticket (same MiniLM model as the archive) so search can find it by meaning."""
    from .retrieval import embed_texts

    text = build_ticket_text(subject, body)
    _ticket_index().upsert(ids=[f"t{ticket_id}"], embeddings=embed_texts([text]), documents=[text[:2000]],
                           metadatas=[{"ticket_id": int(ticket_id), "source": source, "fp": _fingerprint(text)}])


def sync_ticket_index() -> int:
    """Keep the meaning index in step with the tickets table.

    Adds tickets that are not indexed yet (e.g. saved before this feature), re-indexes tickets whose
    text no longer matches the stored fingerprint (e.g. after the database was reset) and removes
    entries for tickets that no longer exist. Returns the number of tickets (re)indexed.
    """
    from .retrieval import embed_texts

    col = _ticket_index()
    got = col.get(include=["metadatas"])
    indexed = {i: (m or {}).get("fp") for i, m in zip(got["ids"], got["metadatas"])}
    rows = fetchall("SELECT id, subject, body, source FROM tickets")
    current = {f"t{r['id']}": r for r in rows}
    stale = [i for i in indexed if i not in current]
    if stale:
        col.delete(ids=stale)
    todo = []
    for key, r in current.items():
        text = build_ticket_text(r["subject"], r["body"])
        if indexed.get(key) != _fingerprint(text):
            todo.append((r, text))
    for start in range(0, len(todo), 64):
        batch = todo[start:start + 64]
        col.upsert(ids=[f"t{r['id']}" for r, _ in batch], embeddings=embed_texts([t for _, t in batch]),
                   documents=[t[:2000] for _, t in batch],
                   metadatas=[{"ticket_id": int(r["id"]), "source": r["source"], "fp": _fingerprint(t)}
                              for r, t in batch])
    return len(todo)


def search_tickets(q: str, k: int = 8, min_similarity: float = 0.35) -> list[dict]:
    """Your tickets matching a query by words (any meaningful word) or by meaning.

    Each result carries `matched_words` and `similarity` so the UI can say why it matched.
    """
    q = (q or "").strip()
    if not q:
        return []
    found: dict[int, dict] = {}
    for r in list_tickets(q=q, limit=50):
        if r.get("matched_words") or str(r["id"]) == q.lstrip("#"):
            found[r["id"]] = {**r, "similarity": None}
    try:
        from .retrieval import embed_texts

        sync_ticket_index()
        col = _ticket_index()
        n = col.count()
        if n:
            res = col.query(query_embeddings=embed_texts([q]), n_results=min(k * 2, n),
                            include=["metadatas", "distances"])
            for meta, dist in zip(res["metadatas"][0], res["distances"][0]):
                sim = max(0.0, 1.0 - float(dist))
                tid = int(meta.get("ticket_id", -1))
                if sim < min_similarity:
                    continue
                if tid in found:
                    found[tid]["similarity"] = sim
                else:
                    t = get_ticket(tid)
                    if t:
                        found[tid] = {**t, "matched_words": [], "similarity": sim}
    except Exception:
        pass  # keyword results still work if the vector index is unavailable

    def rank(r):
        return (-(r.get("similarity") or 0) - 0.1 * len(r.get("matched_words") or []), -r["id"])

    return sorted(found.values(), key=rank)[:k]


def set_status(ticket_id: int, status: str, actor: str | None = None) -> None:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    execute("UPDATE tickets SET status = ?, updated_at = datetime('now') WHERE id = ?", (status, ticket_id))
    log_activity("ticket", f"Ticket #{ticket_id} marked {STATUS_LABELS[status].lower()}",
                 ref_type="ticket", ref_id=ticket_id, actor=actor)
    t = get_ticket(ticket_id)
    if t and t.get("requester_login") and t["requester_login"] != actor:
        notify(f"Your ticket #{ticket_id} is now {STATUS_LABELS[status].lower()}", page="my_tickets",
               ref_id=ticket_id, target_login=t["requester_login"])


def correct_priority(ticket_id: int, priority: str, actor: str | None = None) -> None:
    """Manual correction. Stored next to the prediction so corrections can be exported for retraining."""
    if priority not in PRIORITIES:
        raise ValueError(f"priority must be one of {PRIORITIES}")
    t = get_ticket(ticket_id)
    if not t:
        raise ValueError(f"Ticket {ticket_id} not found")
    if priority == t["predicted_priority"]:
        execute("UPDATE tickets SET final_priority = NULL, corrected_by = NULL, corrected_at = NULL, "
                "updated_at = datetime('now') WHERE id = ?", (ticket_id,))
        msg = f"Ticket #{ticket_id} priority reset to the model's prediction ({priority})"
    else:
        execute("UPDATE tickets SET final_priority = ?, corrected_by = ?, corrected_at = datetime('now'), "
                "updated_at = datetime('now') WHERE id = ?", (priority, actor, ticket_id))
        msg = f"Ticket #{ticket_id} priority corrected from {t['predicted_priority']} to {priority}"
    log_activity("correction", msg, ref_type="ticket", ref_id=ticket_id, actor=actor)


def ticket_stats(include_archive: bool = True) -> dict:
    src = "" if include_archive else "WHERE source != 'archive'"
    total = fetchone(f"SELECT COUNT(*) AS n FROM tickets {src}")["n"]
    by_prio = {r["p"]: r["n"] for r in fetchall(
        f"SELECT COALESCE(final_priority, predicted_priority) AS p, COUNT(*) AS n FROM tickets {src} GROUP BY p")}
    by_status = {r["status"]: r["n"] for r in fetchall(
        f"SELECT status, COUNT(*) AS n FROM tickets {src} GROUP BY status")}
    open_high = fetchone(
        "SELECT COUNT(*) AS n FROM tickets WHERE status IN ('open','in_progress') "
        "AND COALESCE(final_priority, predicted_priority) = 'high'" + ("" if include_archive else " AND source != 'archive'")
    )["n"]
    manual = fetchone(
        "SELECT COUNT(*) AS n, AVG(confidence) AS conf, "
        "SUM(CASE WHEN final_priority IS NOT NULL AND final_priority != predicted_priority THEN 1 ELSE 0 END) AS corrected "
        "FROM tickets WHERE source = 'manual'"
    )
    n_manual = int(manual["n"] or 0)
    corrected = int(manual["corrected"] or 0)
    return {
        "total": int(total or 0),
        "open": int(by_status.get("open", 0)) + int(by_status.get("in_progress", 0)),
        "by_priority": {p: int(by_prio.get(p, 0)) for p in PRIORITIES},
        "by_status": {s: int(by_status.get(s, 0)) for s in STATUSES},
        "open_high": int(open_high or 0),
        "manual_count": n_manual,
        "avg_confidence": float(manual["conf"]) if manual["conf"] is not None else None,
        "corrected": corrected,
        "agreement_pct": round(100.0 * (n_manual - corrected) / n_manual, 1) if n_manual else None,
    }


def daily_counts(days: int = 30, include_archive: bool = False) -> list[dict]:
    src = "" if include_archive else "AND source != 'archive'"
    return fetchall(
        f"""
        SELECT date(created_at, 'localtime') AS day,
               COALESCE(final_priority, predicted_priority) AS priority, COUNT(*) AS n
        FROM tickets
        WHERE created_at >= datetime('now', ?) {src}
        GROUP BY day, priority ORDER BY day
        """,
        (f"-{int(days)} days",),
    )


def correction_pairs() -> list[dict]:
    return fetchall(
        "SELECT predicted_priority AS predicted, final_priority AS corrected, COUNT(*) AS n FROM tickets "
        "WHERE source = 'manual' AND final_priority IS NOT NULL AND final_priority != predicted_priority "
        "GROUP BY predicted_priority, final_priority"
    )


def archive_available() -> int:
    """Size of the historical ticket index (talks to ChromaDB directly; no embedding model load)."""
    try:
        import chromadb
        from chromadb.config import Settings

        from .config import CHROMA_DIR, COLLECTION_NAME

        if not CHROMA_DIR.exists():
            return 0
        client = chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
        return int(client.get_collection(COLLECTION_NAME).count())
    except Exception:
        return 0


def import_archive_samples(n: int = 40, actor: str | None = None, seed: int | None = None) -> int:
    """Copy real historical tickets from the knowledge base into the ticket list.

    Each one is re-scored by the model; the dataset's own label is kept as
    reference_priority. These tickets were in the training data, so they are
    marked source='archive' and excluded from model-agreement statistics.
    """
    from .retrieval import get_collection

    col = get_collection()
    total = col.count()
    if total == 0:
        return 0
    existing = {r["subject"] for r in fetchall("SELECT subject FROM tickets WHERE source = 'archive'")}
    rng = random.Random(seed)
    offsets = rng.sample(range(total), min(total, n * 3))
    added = 0
    for off in offsets:
        if added >= n:
            break
        got = col.get(limit=1, offset=off, include=["documents", "metadatas"])
        if not got["documents"]:
            continue
        doc = (got["documents"][0] or "").replace("\\n", "\n").strip()
        meta = got["metadatas"][0] or {}
        if meta.get("source") != "dataset" or not doc:
            continue
        subject, _, body = doc.partition(". ")
        if not body:
            subject, body = doc[:80], doc
        if subject in existing:
            continue
        pred = predict_ticket(subject, body, with_similar=False)
        create_ticket(subject, body, pred, actor=actor, source="archive", status="resolved",
                      reference_priority=str(meta.get("priority") or "") or None, run_automation=False)
        existing.add(subject)
        added += 1
    if added:
        log_activity("import", f"Imported {added} historical tickets from the archive", actor=actor)
    return added


# ---------------------------------------------------------------- role-based ticket workflow
#
# Every function below takes the signed-in account (a dict from copilot.auth) and checks on
# the server what that role may do, so the rules hold no matter how the request was made:
#   Employees  submit tickets, see their own tickets and tickets assigned to them, work and
#              resolve assigned tickets, and confirm or reopen their own resolved tickets.
#   Senior Analysts see everything, approve or reject suggested solutions, assign, resolve,
#              change status and correct priorities.

def _require(actor: dict | None, *roles: str) -> dict:
    from .auth import require_role

    return require_role(actor, *roles)


def can_view(actor: dict, ticket: dict) -> bool:
    return actor["role"] == "analyst" or actor["id"] in (ticket.get("requester_account_id"),
                                                         ticket.get("assignee_account_id"))


def get_ticket_for(ticket_id: int, actor: dict) -> dict:
    """A ticket the actor is allowed to see (raises PermissionDenied otherwise)."""
    from .auth import PermissionDenied

    me = _require(actor, "employee", "analyst")
    t = get_ticket(ticket_id)
    if not t or not can_view(me, t):
        raise PermissionDenied("You don't have access to this ticket.")
    return t


def submit_ticket(subject: str, body: str, actor: dict) -> dict:
    """Employee (or analyst) raises a ticket: the model predicts priority, the similarity engine
    looks for a resolved ticket with a reusable solution, and the ticket is routed to review or
    to the New / Escalated queue."""
    me = _require(actor, "employee", "analyst")
    subject, body = (subject or "").strip(), (body or "").strip()
    if len(subject) < 4:
        raise ValueError("Give the ticket a short subject (at least 4 characters).")
    if len(body) < 10:
        raise ValueError("Describe the problem in a sentence or two.")
    pred = predict_ticket(subject, body, with_similar=True)
    out = create_ticket(subject, body, pred, requester=me["name"], actor=me["login_id"],
                        requester_account_id=me["id"])
    return {**out, "prediction": pred, "ticket": get_ticket(out["ticket_id"])}


def queue_counts() -> dict:
    out = {}
    for name, cond in _QUEUES.items():
        out[name] = int(fetchone(f"SELECT COUNT(*) AS n FROM tickets t WHERE {cond}")["n"])
    out["high_active"] = int(fetchone(
        f"SELECT COUNT(*) AS n FROM tickets t WHERE {_QUEUES['active']} "
        "AND COALESCE(t.final_priority, t.predicted_priority) = 'high'")["n"])
    return out


def my_ticket_counts(account_id: int) -> dict:
    rows = fetchall("SELECT status, review_status, assignee_account_id FROM tickets WHERE requester_account_id = ?",
                    (account_id,))
    stages = [_stage(r) for r in rows]
    assigned = fetchone("SELECT COUNT(*) AS n FROM tickets WHERE assignee_account_id = ? "
                        "AND status IN ('open', 'in_progress')", (account_id,))["n"]
    return {
        "total": len(rows),
        "active": sum(s not in ("resolved", "closed") for s in stages),
        "suggested": stages.count("suggested"),
        "self_resolved": sum(r["review_status"] == "self_resolved" for r in rows),
        "escalated": stages.count("escalated"),
        "in_progress": stages.count("in_progress") + stages.count("assigned"),
        "resolved": stages.count("resolved") + stages.count("closed"),
        "assigned_to_me": int(assigned or 0),
    }


def _notify_requester(t: dict, message: str, actor_login: str | None) -> None:
    if t.get("requester_login") and t["requester_login"] != actor_login:
        notify(message, page="my_tickets", ref_id=t["id"], target_login=t["requester_login"])


def _add_to_knowledge_base(t: dict, resolution: str) -> int | None:
    """Feedback loop: a resolved ticket becomes a searchable past solution for future tickets."""
    try:
        from .retrieval import upsert

        return upsert(question=build_ticket_text(t["subject"], t["body"]), resolution=resolution,
                      ticket_id=2_000_000 + int(t["id"]), ticket_type=t.get("predicted_type") or "Request",
                      priority=t.get("priority") or "medium", queue="pragyaan_resolved", source="pragyaan")
    except Exception:
        return None


def approve_suggestion(ticket_id: int, actor: dict, solution: str | None = None) -> dict:
    """Senior Analyst resolves a ticket with its recommended solution (optionally edited) on the
    requester's behalf, e.g. for tickets they triaged themselves. The requester is notified."""
    me = _require(actor, "analyst")
    t = get_ticket(ticket_id)
    if not t:
        raise ValueError(f"Ticket #{ticket_id} not found.")
    if t["review_status"] not in ("pending", "suggested") or t["status"] != "open":
        raise ValueError(f"Ticket #{ticket_id} has no recommended solution waiting.")
    text = (solution if solution is not None else t["suggested_solution"] or "").strip()
    if len(text) < 5:
        raise ValueError("The solution text is empty.")
    edited = text != (t["suggested_solution"] or "").strip()
    execute("UPDATE tickets SET review_status = 'approved', status = 'resolved', resolution = ?, resolved_by = ?, "
            "resolved_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
            (text, me["login_id"], ticket_id))
    log_activity("ticket", f"Suggested solution for ticket #{ticket_id} approved{' with edits' if edited else ''}; "
                 "ticket resolved", ref_type="ticket", ref_id=ticket_id, actor=me["login_id"])
    if edited:
        _add_to_knowledge_base(t, text)
    _notify_requester(t, f"A solution for your ticket #{ticket_id} was approved", me["login_id"])
    return get_ticket(ticket_id)


def reject_suggestion(ticket_id: int, actor: dict, reason: str | None = None) -> dict:
    """Senior Analyst decides the recommended solution doesn't fit: the ticket is escalated."""
    me = _require(actor, "analyst")
    t = get_ticket(ticket_id)
    if not t or t["review_status"] not in ("pending", "suggested"):
        raise ValueError(f"Ticket #{ticket_id} has no recommended solution waiting.")
    execute("UPDATE tickets SET review_status = 'rejected', updated_at = datetime('now') WHERE id = ?", (ticket_id,))
    why = f" ({reason.strip()[:120]})" if reason and reason.strip() else ""
    log_activity("ticket", f"Suggested solution for ticket #{ticket_id} rejected{why}; moved to escalated tickets",
                 ref_type="ticket", ref_id=ticket_id, actor=me["login_id"])
    _notify_requester(t, f"Your ticket #{ticket_id} was escalated to a Senior Analyst", me["login_id"])
    return get_ticket(ticket_id)


def assign_ticket(ticket_id: int, assignee_account_id: int | None, actor: dict) -> dict:
    """Senior Analyst assigns (or unassigns) a ticket to an active team member."""
    from .auth import get_account

    me = _require(actor, "analyst")
    t = get_ticket(ticket_id)
    if not t:
        raise ValueError(f"Ticket #{ticket_id} not found.")
    if t["status"] in ("resolved", "closed"):
        raise ValueError(f"Ticket #{ticket_id} is already {t['status']}. Reopen it first.")
    if assignee_account_id is None:
        execute("UPDATE tickets SET assignee_account_id = NULL, updated_at = datetime('now') WHERE id = ?",
                (ticket_id,))
        log_activity("ticket", f"Ticket #{ticket_id} unassigned", ref_type="ticket", ref_id=ticket_id,
                     actor=me["login_id"])
        return get_ticket(ticket_id)
    who = get_account(int(assignee_account_id))
    if not who or not who["is_active"]:
        raise ValueError("Choose an active team member.")
    if who["id"] == t.get("assignee_account_id"):
        return t
    execute("UPDATE tickets SET assignee_account_id = ?, review_status = CASE WHEN review_status IN "
            "('pending', 'suggested') THEN 'rejected' ELSE review_status END, updated_at = datetime('now') WHERE id = ?",
            (who["id"], ticket_id))
    log_activity("ticket", f"Ticket #{ticket_id} assigned to {who['name']} ({who['login_id']})",
                 ref_type="ticket", ref_id=ticket_id, actor=me["login_id"])
    if who["id"] != me["id"]:
        notify(f"Ticket #{ticket_id} was assigned to you: {t['subject'][:70]}",
               level="high" if t["priority"] == "high" else "info", page="my_tickets", ref_id=ticket_id,
               target_login=who["login_id"])
    _notify_requester(t, f"Your ticket #{ticket_id} was assigned to {who['name']}", me["login_id"])
    return get_ticket(ticket_id)


def start_work(ticket_id: int, actor: dict) -> dict:
    """The assignee (or an analyst) marks a ticket in progress."""
    from .auth import PermissionDenied

    me = _require(actor, "employee", "analyst")
    t = get_ticket(ticket_id)
    if not t:
        raise ValueError(f"Ticket #{ticket_id} not found.")
    if me["role"] != "analyst" and t.get("assignee_account_id") != me["id"]:
        raise PermissionDenied("Only the assignee or a Senior Analyst can update this ticket.")
    if t["status"] != "open":
        raise ValueError(f"Ticket #{ticket_id} is {STATUS_LABELS[t['status']].lower()}.")
    set_status(ticket_id, "in_progress", actor=me["login_id"])
    return get_ticket(ticket_id)


def resolve_ticket(ticket_id: int, resolution: str, actor: dict, add_to_kb: bool = True) -> dict:
    """Resolve with a written solution (Senior Analyst, or the employee it is assigned to).
    The solution is added to the knowledge base so similar future tickets can reuse it."""
    from .auth import PermissionDenied

    me = _require(actor, "employee", "analyst")
    t = get_ticket(ticket_id)
    if not t:
        raise ValueError(f"Ticket #{ticket_id} not found.")
    if me["role"] != "analyst" and t.get("assignee_account_id") != me["id"]:
        raise PermissionDenied("Only the assignee or a Senior Analyst can resolve this ticket.")
    if t["status"] in ("resolved", "closed"):
        raise ValueError(f"Ticket #{ticket_id} is already {t['status']}.")
    text = (resolution or "").strip()
    if len(text) < 10:
        raise ValueError("Write the solution in a sentence or two so the employee (and future tickets) can use it.")
    review = "rejected" if t["review_status"] in ("pending", "suggested") else t["review_status"]
    execute("UPDATE tickets SET status = 'resolved', resolution = ?, resolved_by = ?, resolved_at = datetime('now'), "
            "review_status = ?, updated_at = datetime('now') WHERE id = ?",
            (text, me["login_id"], review, ticket_id))
    kb = _add_to_knowledge_base(t, text) if add_to_kb else None
    log_activity("ticket", f"Ticket #{ticket_id} resolved by {me['name']}"
                 + ("; solution added to the knowledge base" if kb else ""),
                 ref_type="ticket", ref_id=ticket_id, actor=me["login_id"])
    _notify_requester(t, f"Your ticket #{ticket_id} was resolved", me["login_id"])
    return get_ticket(ticket_id)


def confirm_resolved(ticket_id: int, actor: dict) -> dict:
    """The employee who raised the ticket confirms the solution worked: the ticket is closed."""
    from .auth import PermissionDenied

    me = _require(actor, "employee", "analyst")
    t = get_ticket(ticket_id)
    if not t:
        raise ValueError(f"Ticket #{ticket_id} not found.")
    if t.get("requester_account_id") != me["id"] and me["role"] != "analyst":
        raise PermissionDenied("Only the person who raised this ticket can confirm it.")
    if t["status"] != "resolved":
        raise ValueError(f"Ticket #{ticket_id} isn't resolved yet.")
    execute("UPDATE tickets SET status = 'closed', updated_at = datetime('now') WHERE id = ?", (ticket_id,))
    log_activity("ticket", f"Ticket #{ticket_id} closed: {me['name']} confirmed the solution worked",
                 ref_type="ticket", ref_id=ticket_id, actor=me["login_id"])
    return get_ticket(ticket_id)


def reopen_ticket(ticket_id: int, actor: dict, reason: str | None = None) -> dict:
    """Reopen a resolved ticket (its requester or a Senior Analyst). It goes back to the
    escalated queue, or to its assignee if it has one."""
    from .auth import PermissionDenied

    me = _require(actor, "employee", "analyst")
    t = get_ticket(ticket_id)
    if not t:
        raise ValueError(f"Ticket #{ticket_id} not found.")
    if t.get("requester_account_id") != me["id"] and me["role"] != "analyst":
        raise PermissionDenied("Only the person who raised this ticket or a Senior Analyst can reopen it.")
    if t["status"] not in ("resolved", "closed"):
        raise ValueError(f"Ticket #{ticket_id} is still open.")
    review = {"approved": "rejected", "self_resolved": "declined", "suggested": "declined",
              "pending": "declined"}.get(t["review_status"], t["review_status"])
    execute("UPDATE tickets SET status = 'open', review_status = ?, updated_at = datetime('now') WHERE id = ?",
            (review, ticket_id))
    why = f": {reason.strip()[:140]}" if reason and reason.strip() else ""
    log_activity("ticket", f"Ticket #{ticket_id} reopened by {me['name']}{why}", ref_type="ticket",
                 ref_id=ticket_id, actor=me["login_id"])
    target = t.get("assignee_login")
    if target and target != me["login_id"]:
        notify(f"Ticket #{ticket_id} was reopened{why}", level="info", page="my_tickets", ref_id=ticket_id,
               target_login=target)
    else:
        notify(f"Ticket #{ticket_id} was reopened{why}", level="info", page="review", ref_id=ticket_id)
    return get_ticket(ticket_id)


# ---------------------------------------------------------------- employee self-service

def _own_ticket(ticket_id: int, actor: dict) -> tuple[dict, dict]:
    from .auth import PermissionDenied

    me = _require(actor, "employee", "analyst")
    t = get_ticket(ticket_id)
    if not t:
        raise ValueError(f"Ticket #{ticket_id} not found.")
    if t.get("requester_account_id") != me["id"]:
        raise PermissionDenied("Only the person who raised this ticket can do this.")
    return me, t


def accept_suggestion(ticket_id: int, actor: dict) -> dict:
    """The employee says the recommended solution fixed it: the ticket is closed as self-resolved.
    No Senior Analyst action is needed; it shows up on their dashboard as completed."""
    me, t = _own_ticket(ticket_id, actor)
    if t["status"] != "open" or t["review_status"] not in ("suggested", "pending"):
        raise ValueError(f"Ticket #{ticket_id} has no recommended solution waiting for you.")
    execute("UPDATE tickets SET status = 'closed', review_status = 'self_resolved', resolution = suggested_solution, "
            "resolved_by = ?, resolved_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
            (me["login_id"], ticket_id))
    log_activity("ticket", f"Ticket #{ticket_id} closed by {me['name']}: the recommended solution from resolved "
                 f"ticket #{t['match_ticket_id']} worked (self-service)", ref_type="ticket", ref_id=ticket_id,
                 actor=me["login_id"])
    return get_ticket(ticket_id)


def decline_suggestion(ticket_id: int, actor: dict, reason: str | None = None) -> dict:
    """The employee says the recommended solution didn't help: escalate to the Senior Analysts."""
    me, t = _own_ticket(ticket_id, actor)
    if t["status"] != "open" or t["review_status"] not in ("suggested", "pending"):
        raise ValueError(f"Ticket #{ticket_id} has no recommended solution waiting for you.")
    execute("UPDATE tickets SET review_status = 'declined', updated_at = datetime('now') WHERE id = ?", (ticket_id,))
    why = f": {reason.strip()[:160]}" if reason and reason.strip() else ""
    log_activity("ticket", f"Ticket #{ticket_id} escalated by {me['name']}: the recommended solution didn't help{why}",
                 ref_type="ticket", ref_id=ticket_id, actor=me["login_id"])
    notify(f"{'High-priority t' if t['priority'] == 'high' else 'T'}icket #{ticket_id} escalated: the recommended "
           f"solution didn't help ({t['subject'][:60]})", level="high" if t["priority"] == "high" else "info",
           page="review", ref_id=ticket_id)
    return get_ticket(ticket_id)


def self_resolve(subject: str, body: str, solution: dict, actor: dict) -> dict:
    """The employee found the answer among the recommendations before raising a ticket. The search
    is recorded as a ticket that is already closed (self-resolved), with the solution that worked,
    so Senior Analysts can see it on their dashboard without having to act on it.

    `solution` is a recommendation from find_solutions(): a resolved ticket ({'ticket_id', 'answer',
    'similarity'}) or a Knowledge Hub passage ({'doc_id', 'title', 'text', 'similarity'})."""
    me = _require(actor, "employee", "analyst")
    subject, body = (subject or "").strip(), (body or "").strip()
    if len(subject) < 4 and len(body) < 4:
        raise ValueError("Describe the problem first.")
    subject = subject or body[:160]
    body = body or subject
    if solution.get("doc_id") is not None:
        text = f"From the Knowledge Hub document \"{solution['title']}\":\n{solution['text'].strip()}"
        source = f"Knowledge Hub document \"{solution['title']}\""
        match_id = None
    else:
        text = (solution.get("answer") or "").strip()
        source = f"resolved ticket #{solution['ticket_id']}"
        match_id = int(solution["ticket_id"])
    if not text:
        raise ValueError("That recommendation has no solution text.")
    pred = predict_ticket(subject, body, with_similar=False)
    p = pred["probabilities"]
    tid = execute(
        """
        INSERT INTO tickets (subject, body, requester, predicted_priority, prob_low, prob_medium, prob_high,
                             confidence, severity_score, reason_terms, predicted_type, model_name, status, source,
                             created_by, requester_account_id, match_ticket_id, match_similarity, suggested_solution,
                             review_status, resolution, resolved_by, resolved_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'closed', 'manual', ?, ?, ?, ?, ?, 'self_resolved', ?, ?,
                datetime('now'))
        """,
        (subject[:200], body, me["name"], pred["priority"], p["low"], p["medium"], p["high"], pred["confidence"],
         pred["score"], json.dumps(pred.get("top_terms") or []), pred.get("type"), pred.get("model_name"),
         me["login_id"], me["id"], match_id, float(solution.get("similarity") or 0), text, text, me["login_id"]),
    )
    log_activity("ticket", f"Ticket #{tid} solved by {me['name']} with a recommended solution from {source} "
                 f"({float(solution.get('similarity') or 0):.0%} match), no escalation needed",
                 ref_type="ticket", ref_id=tid, actor=me["login_id"])
    try:
        index_ticket(tid, subject, body)
    except Exception:
        pass
    return get_ticket(tid)


def close_ticket(ticket_id: int, actor: dict, note: str | None = None) -> dict:
    """The employee closes their own open ticket because the issue is solved (for example after an
    answer from the assistant, or it fixed itself)."""
    me, t = _own_ticket(ticket_id, actor)
    if t["status"] not in ("open", "in_progress"):
        raise ValueError(f"Ticket #{ticket_id} is already {t['status']}.")
    note = (note or "").strip()
    execute("UPDATE tickets SET status = 'closed', resolution = COALESCE(NULLIF(?, ''), resolution), resolved_by = ?, "
            "resolved_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
            (note, me["login_id"], ticket_id))
    log_activity("ticket", f"Ticket #{ticket_id} closed by {me['name']}: issue solved"
                 + (f" ({note[:120]})" if note else ""), ref_type="ticket", ref_id=ticket_id, actor=me["login_id"])
    if t.get("assignee_login") and t["assignee_login"] != me["login_id"]:
        notify(f"Ticket #{ticket_id} was closed by {me['name']}: their issue is solved", page="my_tickets",
               ref_id=ticket_id, target_login=t["assignee_login"])
    return get_ticket(ticket_id)


def self_service_stats(days: int = 7) -> dict:
    """How many tickets employees closed with a recommended solution (no analyst work needed)."""
    row = fetchone("SELECT COUNT(*) AS n, SUM(CASE WHEN resolved_at >= datetime('now', ?) THEN 1 ELSE 0 END) AS recent "
                   "FROM tickets WHERE review_status = 'self_resolved'", (f"-{int(days)} days",))
    manual = fetchone("SELECT COUNT(*) AS n FROM tickets WHERE source = 'manual' AND requester_account_id IS NOT NULL")
    total, mine = int(row["n"] or 0), int(manual["n"] or 0)
    return {"total": total, "recent": int(row["recent"] or 0),
            "rate_pct": round(100.0 * total / mine, 1) if mine else None}


def ticket_timeline(ticket_id: int) -> list[dict]:
    """Everything that happened to a ticket, oldest first (from the activity log)."""
    return fetchall("SELECT * FROM activity WHERE ref_type = 'ticket' AND ref_id = ? ORDER BY id", (ticket_id,))


def workload() -> list[dict]:
    """Active and resolved tickets per team member (for assignment and team management)."""
    return fetchall(
        """
        SELECT a.id, a.login_id, a.name, a.role, a.department, a.title, a.is_active,
               SUM(CASE WHEN t.status IN ('open', 'in_progress') THEN 1 ELSE 0 END) AS active,
               SUM(CASE WHEN t.status IN ('open', 'in_progress')
                         AND COALESCE(t.final_priority, t.predicted_priority) = 'high' THEN 1 ELSE 0 END) AS active_high,
               SUM(CASE WHEN t.status IN ('resolved', 'closed') THEN 1 ELSE 0 END) AS resolved
        FROM accounts a LEFT JOIN tickets t ON t.assignee_account_id = a.id
        GROUP BY a.id ORDER BY a.is_active DESC, a.role DESC, a.name COLLATE NOCASE
        """
    )


def search_tickets_for(q: str, actor: dict, k: int = 8) -> list[dict]:
    """search_tickets limited to what the actor may see (employees: own and assigned tickets)."""
    me = _require(actor, "employee", "analyst")
    if me["role"] == "analyst":
        return search_tickets(q, k=k)
    return [t for t in search_tickets(q, k=50) if can_view(me, t)][:k]


def find_solutions(text: str, k: int = 3, min_similarity: float = 0.40) -> dict:
    """Existing solution recommendations for a problem description: the closest resolved tickets
    (with their recorded answers) and matching Knowledge Hub passages. `strong` marks matches above
    the threshold PRAGYAAN uses to reuse a solution automatically."""
    from .config import DOC_SIM_THRESHOLD, SIM_THRESHOLD

    text = (text or "").strip()
    out = {"tickets": [], "documents": [], "errors": []}
    if len(text) < 4:
        return out
    try:
        from .retrieval import search

        for h in search(text, k=k + 2):
            if h.similarity >= min_similarity and (h.answer or "").strip():
                out["tickets"].append({"ticket_id": h.ticket_id, "similarity": float(h.similarity),
                                       "snippet": h.snippet, "answer": h.answer,
                                       "strong": h.similarity >= SIM_THRESHOLD,
                                       "source": h.metadata.get("source")})
        out["tickets"] = out["tickets"][:k]
    except Exception as e:
        out["errors"].append(f"Resolved-ticket search unavailable: {e}")
    try:
        from .knowledge import search_documents

        out["documents"] = [dict(h, strong=h["similarity"] >= DOC_SIM_THRESHOLD)
                            for h in search_documents(text, k=k) if h["similarity"] >= min_similarity - 0.05]
    except Exception as e:
        out["errors"].append(f"Document search unavailable: {e}")
    return out
