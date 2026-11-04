"""PRAGYAAN platform tests: auth, triage + corrections, automation, knowledge hub,
assistant routing, reports and search. Uses a temporary SQLite DB and document index;
the historical ticket knowledge base is only read, never modified."""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from copilot import db, knowledge, triage  # noqa: E402
from copilot.config import MODELS_DIR  # noqa: E402

pytestmark = pytest.mark.skipif(
    not (MODELS_DIR / "severity.joblib").exists(), reason="Models not built yet"
)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "SQLITE_PATH", tmp_path / "test.db")
    db._initialized.clear()
    monkeypatch.setattr(knowledge, "CHROMA_DIR", tmp_path / "chroma_docs")
    monkeypatch.setattr(knowledge, "DOCS_DIR", tmp_path / "documents")
    monkeypatch.setattr(triage, "CHROMA_DIR", tmp_path / "chroma_tickets")
    yield
    db._initialized.clear()


def test_accounts_roles_portals_and_hashing():
    from copilot.auth import (AuthError, PermissionDenied, authenticate, create_account, needs_setup,
                              require_role)

    assert needs_setup()
    lead = create_account("SA-001", "Asha Rao", "analyst", "correct-horse-1")
    assert not needs_setup()
    emp = create_account("EMP-1042", "Ravi Kumar", "employee", "battery-staple-2", department="IT", created_by=lead)
    assert lead["role"] == "analyst" and emp["role"] == "employee" and emp["department"] == "IT"
    # IDs are case-insensitive; each ID only works on its own portal
    assert authenticate("sa-001", "correct-horse-1", "analyst")["name"] == "Asha Rao"
    assert authenticate("EMP-1042", "battery-staple-2", "employee")["id"] == emp["id"]
    with pytest.raises(AuthError):
        authenticate("EMP-1042", "battery-staple-2", "analyst")  # employee on the analyst portal
    with pytest.raises(AuthError):
        authenticate("SA-001", "correct-horse-1", "employee")
    with pytest.raises(AuthError) as wrong:
        authenticate("SA-001", "wrong-password-9", "analyst")
    with pytest.raises(AuthError) as unknown:
        authenticate("NOBODY-1", "wrong-password-9", "analyst")
    assert str(wrong.value) == str(unknown.value)  # no hint which IDs exist
    # validation
    for bad in [("EMP-1042", "Dup", "employee", "another-pass-3"), ("x", "Short id", "employee", "another-pass-3"),
                ("a@b.com", "Email id", "employee", "another-pass-3"), ("EMP-2", "Weak", "employee", "12345678"),
                ("EMP-3", "Short pw", "employee", "abc1")]:
        with pytest.raises(AuthError):
            create_account(*bad, created_by=lead)
    with pytest.raises(PermissionDenied):  # employees can't create accounts
        create_account("EMP-9", "Sneaky", "analyst", "sneaky-pass-1", created_by=emp)
    with pytest.raises(PermissionDenied):
        require_role(emp, "analyst")
    stored = db.fetchone("SELECT password_hash FROM accounts WHERE login_id = 'SA-001'")["password_hash"]
    assert "correct-horse-1" not in stored and stored.startswith("pbkdf2_sha256$200000$")


def test_lockout_sessions_and_password_changes():
    from copilot.auth import (AuthError, authenticate, change_password, create_account, create_session,
                              request_password_reset, list_reset_requests, reset_password, revoke_session,
                              session_account, update_account)

    lead = create_account("SA-001", "Asha Rao", "analyst", "correct-horse-1")
    emp = create_account("EMP-7", "Meera N", "employee", "first-pass-11", created_by=lead)
    for _ in range(5):
        with pytest.raises(AuthError):
            authenticate("EMP-7", "nope-nope-1", "employee")
    with pytest.raises(AuthError, match="Too many failed attempts"):
        authenticate("EMP-7", "first-pass-11", "employee")  # locked even with the right password
    db.execute("UPDATE accounts SET locked_until = datetime('now', '-1 minutes') WHERE login_id = 'EMP-7'")
    assert authenticate("EMP-7", "first-pass-11", "employee")["login_id"] == "EMP-7"

    token = create_session(emp["id"], remember=True)
    assert session_account(token)["login_id"] == "EMP-7"
    assert db.fetchone("SELECT COUNT(*) AS n FROM sessions WHERE token_hash = ?", (token,))["n"] == 0  # hashed
    revoke_session(token)
    assert session_account(token) is None
    expired = create_session(emp["id"])
    db.execute("UPDATE sessions SET expires_at = datetime('now', '-1 minutes')")
    assert session_account(expired) is None

    # forgot password -> analyst issues a temporary password -> forced change
    request_password_reset("EMP-7", "employee")
    request_password_reset("NOBODY", "employee")  # silently ignored
    assert [r["login_id"] for r in list_reset_requests(lead)] == ["EMP-7"]
    live = create_session(emp["id"])
    temp = reset_password(emp["id"], lead)
    assert session_account(live) is None  # reset signs the person out everywhere
    acct = authenticate("EMP-7", temp, "employee")
    assert acct["must_change_password"]
    change_password(acct["id"], None, "brand-new-pass-5")
    assert not authenticate("EMP-7", "brand-new-pass-5", "employee")["must_change_password"]
    with pytest.raises(AuthError):
        change_password(acct["id"], "wrong-current-1", "another-new-pass-6")
    assert list_reset_requests(lead) == []

    # deactivation ends sessions and blocks sign-in; the last analyst can't be removed
    s2 = create_session(emp["id"])
    update_account(emp["id"], lead, is_active=False)
    assert session_account(s2) is None
    with pytest.raises(AuthError, match="deactivated"):
        authenticate("EMP-7", "brand-new-pass-5", "employee")
    with pytest.raises(AuthError):
        update_account(lead["id"], lead, is_active=False)


def test_legacy_users_are_migrated_to_accounts():
    from copilot.auth import authenticate, hash_password

    db.ensure_db()
    db.execute("INSERT INTO users (email, name, role, password_hash) VALUES (?, ?, 'admin', ?)",
               ("Lead@Example.com", "Old Admin", hash_password("legacy-pass-1")))
    db.execute("INSERT INTO users (email, name, role, password_hash) VALUES (?, ?, 'agent', ?)",
               ("agent@example.com", "Old Agent", hash_password("legacy-pass-2")))
    db.execute("DELETE FROM accounts")
    db._initialized.clear()
    db.ensure_db()
    assert authenticate("lead@example.com", "legacy-pass-1", "analyst")["name"] == "Old Admin"
    assert authenticate("agent@example.com", "legacy-pass-2", "employee")["role"] == "employee"


def test_triage_prediction_storage_rules_and_correction():
    from copilot.activity import list_notifications
    from copilot.automation import list_tasks
    from copilot.triage import correct_priority, create_ticket, get_ticket, predict_ticket, ticket_stats

    pred = predict_ticket("Production database outage", "All customers are unable to check out since 9am, revenue impact.")
    probs = pred["probabilities"]
    assert set(probs) == {"low", "medium", "high"}
    assert abs(sum(probs.values()) - 1.0) < 1e-6
    assert pred["priority"] == max(probs, key=probs.get)
    assert pred["confidence"] == pytest.approx(probs[pred["priority"]])
    assert pred["model_name"]

    created = create_ticket("Production database outage", "All customers are unable to check out.",
                            {**pred, "priority": "high"}, actor="lead@example.com")
    tid = created["ticket_id"]
    # default rules: one auto task for high priority, one suggestion
    assert len(created["created"]) == 1 and len(created["suggestions"]) == 1
    assert list_tasks(ticket_id=tid)[0]["priority"] == "high"
    assert any(f"#{tid}" in n["message"] and n["level"] == "high"
               for n in list_notifications("lead@example.com", role="analyst"))
    assert list_notifications("someone", role="employee") == []  # operational alerts go to analysts only

    correct_priority(tid, "medium", actor="lead@example.com")
    t = get_ticket(tid)
    assert t["final_priority"] == "medium" and t["corrected"] and t["priority"] == "medium"
    s = ticket_stats()
    assert s["manual_count"] == 1 and s["corrected"] == 1 and s["agreement_pct"] == 0.0
    correct_priority(tid, "high", actor="lead@example.com")  # back to the prediction
    assert get_ticket(tid)["final_priority"] is None


def test_tasks_status_and_overdue():
    from copilot.automation import create_task, list_tasks, set_task_status, task_stats

    late = create_task("Reply to customer", priority="high", due_at="2000-01-01 00:00:00")
    create_task("Write runbook", priority="low", due_in_hours=48)
    assert task_stats()["overdue"] == 1
    assert {t["id"]: t["overdue"] for t in list_tasks()}[late] == 1
    set_task_status(late, "done")
    st = task_stats()
    assert st["done"] == 1 and st["overdue"] == 0 and st["sla_met_pct"] == 0.0


def _docx(paragraphs: list[str]) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = ('<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
           f'wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


VPN_DOC = (
    "VPN access policy.\n\nNew employees request VPN access through the IT portal under Network > VPN. "
    "Your manager approves the request and access is provisioned within one business day.\n\n"
    "To reset your VPN password, open the self-service portal, choose Reset VPN credentials and "
    "confirm with the code sent to your phone. Passwords expire every 90 days."
)


def test_knowledge_hub_ingest_search_update_delete():
    from copilot.knowledge import (add_document, document_text, extract_text, list_documents,
                                   search_documents, update_document, delete_document)

    assert "Second paragraph" in extract_text("x.docx", _docx(["First paragraph", "Second paragraph"]))
    doc_id = add_document("vpn_policy.txt", VPN_DOC.encode(), collection="IT", tags=["vpn", "access"])
    assert "Reset VPN credentials" in document_text(doc_id)
    hits = search_documents("how do I reset my VPN password")
    assert hits and hits[0]["doc_id"] == doc_id and hits[0]["similarity"] > 0.4
    update_document(doc_id, title="VPN policy 2026", collection="Security", tags="vpn")
    assert list_documents(collection="Security")[0]["title"] == "VPN policy 2026"
    delete_document(doc_id)
    assert list_documents() == [] and search_documents("reset VPN password") == []


def test_assistant_answers_from_documents_and_summarizes():
    from copilot.assistant import answer, history
    from copilot.knowledge import add_document

    add_document("vpn_policy.txt", VPN_DOC.encode(), collection="IT")
    out = answer("How do I reset my VPN password?", user_email="agent@example.com")
    assert out["kind"] == "documents"
    assert out["doc_sources"][0]["title"].lower().startswith("vpn")
    assert db.fetchone("SELECT COUNT(*) AS n FROM escalations")["n"] == 0  # answered, not escalated
    summ = answer("summarize vpn policy", user_email="agent@example.com")
    assert summ["kind"] == "summary" and (summ["sentences"] or summ["summary"])
    assert [m["role"] for m in history("agent@example.com")] == ["user", "assistant", "user", "assistant"]


def test_reports_and_global_search():
    from copilot.globalsearch import search_all
    from copilot.reports import corrections_csv, html_report, tickets_csv
    from copilot.triage import create_ticket, predict_ticket

    pred = predict_ticket("Invoice PDF export broken", "Exporting invoices to PDF fails with a 500 error.")
    tid = create_ticket("Invoice PDF export broken", "Exporting invoices to PDF fails.", pred)["ticket_id"]
    res = search_all("invoice")
    assert res["tickets"][0]["id"] == tid
    assert b"Invoice PDF export broken" in tickets_csv()
    assert corrections_csv().startswith(b"id,subject")
    assert b"PRAGYAAN operations report" in html_report()


def test_ticket_search_by_words_and_meaning():
    from copilot.globalsearch import search_all
    from copilot.triage import create_ticket, predict_ticket, search_tickets

    subject, body = "Payment gateway down, customers cannot complete checkout", \
        "Since 9am all card payments fail with error 502 at checkout."
    tid = create_ticket(subject, body, predict_ticket(subject, body, with_similar=False))["ticket_id"]
    other = create_ticket("Request to update the invoice logo", "Marketing wants the new logo next quarter.",
                          predict_ticket("Request to update the invoice logo", "No urgency.", with_similar=False)
                          )["ticket_id"]
    by_meaning = search_tickets("customers can't pay")
    assert by_meaning and by_meaning[0]["id"] == tid and by_meaning[0]["similarity"] > 0.4
    assert search_tickets("checkout is failing")[0]["id"] == tid
    assert [t["id"] for t in search_tickets(f"#{other}")][0] == other
    assert search_tickets("How do I book a desk on the 4th floor?") == []
    assert search_all("error 502")["tickets"][0]["id"] == tid
    # a reset database must not leave the index describing old tickets
    db.execute("DELETE FROM tickets")
    assert search_tickets("customers can't pay") == []


def _people():
    from copilot.auth import create_account

    lead = create_account("SA-001", "Asha Rao", "analyst", "correct-horse-1")
    emp = create_account("EMP-1", "Ravi Kumar", "employee", "employee-pass-1", created_by=lead)
    other = create_account("EMP-2", "Meera N", "employee", "employee-pass-2", created_by=lead)
    return lead, emp, other


def test_employee_ticket_workflow_self_service_and_escalation(monkeypatch):
    from copilot import retrieval
    from copilot.activity import list_notifications
    from copilot.auth import PermissionDenied
    from copilot.triage import (accept_suggestion, assign_ticket, close_ticket, confirm_resolved, decline_suggestion,
                                find_solutions, get_ticket_for, list_tickets, my_ticket_counts, queue_counts,
                                reopen_ticket, resolve_ticket, search_tickets_for, self_resolve, self_service_stats,
                                submit_ticket)

    kb = []
    monkeypatch.setattr(retrieval, "upsert", lambda **kw: kb.append(kw) or 1)  # never touch the real archive
    lead, emp, other = _people()

    # Close match: the recommended solution goes straight to the employee, not to an analyst
    t1 = submit_ticket("Cannot log in to my account",
                       "I forgot my password and can't log in to my account. How do I reset my password?", emp)["ticket"]
    assert t1["stage"] == "suggested" and t1["suggested_solution"] and t1["match_similarity"] >= 0.55
    assert queue_counts()["waiting"] == 1 and queue_counts()["escalated"] == 0
    assert not list_notifications("SA-001", role="analyst")  # analysts aren't asked to approve anything
    with pytest.raises(PermissionDenied):
        accept_suggestion(t1["id"], other)  # only the requester decides
    done = accept_suggestion(t1["id"], emp)
    assert done["status"] == "closed" and done["review_status"] == "self_resolved"
    assert done["resolution"] == t1["suggested_solution"]
    assert [t["id"] for t in list_tickets(queue="self_resolved")] == [t1["id"]]

    # Close match that didn't help: the employee escalates it to the analysts
    t2 = submit_ticket("Forgot password", "I forgot my password and cannot log in to my account.", emp)["ticket"]
    assert t2["stage"] == "suggested"
    t2 = decline_suggestion(t2["id"], emp, "the reset link never arrives")
    assert t2["stage"] == "escalated" and t2["review_status"] == "declined"
    assert any(f"#{t2['id']} escalated" in n["message"] for n in list_notifications("SA-001", role="analyst"))

    # No close match: escalated directly
    t3 = submit_ticket("Desk booking plugin shows Klingon calendar",
                       "Since the Zorblax 7 rollout the desk booking plugin renders dates in Klingon.", emp)["ticket"]
    assert t3["stage"] == "escalated" and t3["review_status"] == "none"
    assert {t["id"] for t in list_tickets(queue="escalated")} == {t2["id"], t3["id"]}

    # Solved from the recommendations before submitting: recorded as a closed, self-resolved ticket
    rec = find_solutions("How do I reset my password? I forgot it and can't sign in.")
    assert rec["tickets"]
    t4 = self_resolve("Password reset", "How do I reset my password? I forgot it and can't sign in.",
                      rec["tickets"][0], emp)
    assert t4["status"] == "closed" and t4["review_status"] == "self_resolved" and t4["resolution"]
    assert self_service_stats()["total"] == 2

    # employees see only their own tickets
    assert get_ticket_for(t3["id"], emp)["id"] == t3["id"]
    with pytest.raises(PermissionDenied):
        get_ticket_for(t3["id"], other)
    assert search_tickets_for("Klingon calendar", other) == []
    assert search_tickets_for("Klingon calendar", emp)[0]["id"] == t3["id"]
    for call in (lambda: assign_ticket(t3["id"], emp["id"], emp),
                 lambda: resolve_ticket(t3["id"], "I fixed it myself somehow.", other)):
        with pytest.raises(PermissionDenied):
            call()

    # escalated ticket assigned to another employee who resolves it; requester confirms, then reopens
    assign_ticket(t3["id"], other["id"], lead)
    assert get_ticket_for(t3["id"], other)["stage"] == "assigned"
    assert any(f"#{t3['id']} was assigned to you" in n["message"] for n in list_notifications("EMP-2", role="employee"))
    with pytest.raises(ValueError):
        resolve_ticket(t3["id"], "short", other)
    resolve_ticket(t3["id"], "Reset the plugin locale to English in Settings > Region and reload.", other)
    assert kb and kb[-1]["ticket_id"] == 2_000_000 + t3["id"]  # solution added to the archive
    assert any(f"#{t3['id']} was resolved" in n["message"] for n in list_notifications("EMP-1", role="employee"))
    confirm_resolved(t3["id"], emp)
    assert get_ticket_for(t3["id"], emp)["stage"] == "closed"
    reopen_ticket(t3["id"], emp, "Still Klingon after reload")
    assert get_ticket_for(t3["id"], emp)["status"] == "open"

    # the requester can close their own escalated ticket once the issue is solved
    closed = close_ticket(t2["id"], emp, "The reset email finally arrived")
    assert closed["status"] == "closed" and "finally arrived" in closed["resolution"]
    # a self-resolved ticket that is reopened goes to the escalated queue
    reopen_ticket(t1["id"], emp, "worked for a day only")
    assert get_ticket_for(t1["id"], emp)["stage"] == "escalated"
    c = my_ticket_counts(emp["id"])
    assert c["total"] == 4 and c["self_resolved"] == 1 and c["active"] == 2
