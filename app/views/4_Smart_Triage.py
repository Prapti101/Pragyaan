"""Smart Ticket Triage: predict priority with the trained model, store, review and correct."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import ui  # noqa: E402
from copilot.automation import create_task, list_tasks, matching_rules, task_from_rule  # noqa: E402
from copilot.config import EVAL_RESULTS, SIM_THRESHOLD  # noqa: E402
from copilot.auth import PermissionDenied, list_accounts  # noqa: E402
from copilot.triage import (STATUSES, TriageUnavailable, approve_suggestion, assign_ticket,  # noqa: E402
                            correct_priority, create_ticket, get_ticket, list_tickets, model_status, predict_ticket,
                            reject_suggestion, reopen_ticket, resolve_ticket, set_status, ticket_timeline)

P = st.session_state["_pages"]
user = ui.require_role("analyst")
actor = user["login_id"]

ui.page_header("All support tickets",
               "Every ticket with its predicted priority, workflow stage and owner. Triage new tickets with the "
               "priority model, correct priorities, assign and resolve.")

status = model_status()
if not status["ok"]:
    st.error(f"The priority model can't run. {status['message']}", icon=":material/error:")
    st.stop()


@st.cache_data(show_spinner=False)
def test_accuracy() -> float | None:
    try:
        return float(pd.read_csv(EVAL_RESULTS / "severity_test.csv")["accuracy"].iloc[0])
    except Exception:
        return None


focus = st.session_state.pop("focus_ticket", None)
tab_hist, tab_new = st.tabs(["All tickets", "Triage a new ticket"], default="All tickets", key="triage_tabs")

# ---------------------------------------------------------------- new ticket
with tab_new:
    left, right = st.columns([1, 1.15], gap="large")
    with left:
        with st.container(key="card-form"):
            with st.form("triage_form", border=False):
                subject = st.text_input("Subject", placeholder="e.g. Payment gateway returns error 502 at checkout",
                                        max_chars=200)
                body = st.text_area("Description", height=190, max_chars=5000,
                                    placeholder="What happened, who is affected, since when, what was tried…")
                requester = st.text_input("Requester (optional)", placeholder="Name or email")
                go = st.form_submit_button("Analyze ticket", type="primary", icon=":material/bolt:", width="stretch")
            if go:
                if not (subject.strip() or body.strip()):
                    st.warning("Add a subject or a description first.", icon=":material/edit:")
                else:
                    try:
                        with st.spinner("Scoring with the priority model and searching past tickets…"):
                            pred = predict_ticket(subject, body)
                        st.session_state["triage_draft"] = {"subject": subject, "body": body,
                                                            "requester": requester, "pred": pred}
                        st.session_state.pop("triage_saved", None)
                    except TriageUnavailable as e:
                        st.error(str(e), icon=":material/error:")
                    except Exception as e:
                        st.error(f"Prediction failed: {e}", icon=":material/error:")
            acc = test_accuracy()
            if acc:
                st.caption(f"Model accuracy on 1,192 held-out tickets: {acc:.1%}. Low-confidence predictions "
                           "are worth a second look.")

    with right:
        draft = st.session_state.get("triage_draft")
        saved = st.session_state.get("triage_saved")
        if not draft:
            with st.container(key="card-result-empty"):
                ui.empty_state("bolt", "No ticket analyzed yet",
                               "Fill in the subject and description, then choose Analyze ticket. The prediction, "
                               "its probabilities and similar past tickets appear here.")
        else:
            pred = draft["pred"]
            prio = pred["priority"]
            with st.container(key="card-result"):
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap'>"
                    f"<div><div class='pg-muted'>Predicted priority</div>"
                    f"<div style='font-family:Sora;font-size:1.9rem;font-weight:700;color:{ui.PRIORITY_COLORS[prio]}'>"
                    f"{prio.capitalize()}</div></div>"
                    f"<div style='text-align:right'><div class='pg-muted'>Model confidence</div>"
                    f"<div style='font-family:Sora;font-size:1.6rem;font-weight:600'>{pred['confidence']:.0%}</div></div></div>",
                    unsafe_allow_html=True,
                )
                st.markdown(ui.prob_meter(pred["probabilities"], prio), unsafe_allow_html=True)
                bits = [f"Urgency score {pred['score']:.2f} ({pred['bucket']})"]
                if pred.get("type"):
                    bits.append(f"Type: {pred['type']} ({pred['type_confidence']:.0%})")
                st.markdown(" ".join(ui.soft_badge(b) for b in bits), unsafe_allow_html=True)
                if pred["top_terms"]:
                    st.markdown("**Words that drove the score** " + " ".join(f":gray-badge[{t}]" for t in pred["top_terms"]))
                st.caption(f"Model: {pred['model_name']}. Confidence is the share of the forest's trees "
                           "voting for this class.")

                if not saved:
                    st.divider()
                    c1, c2 = st.columns([1.3, 1], vertical_alignment="bottom")
                    final = c1.selectbox("Save with priority", ["high", "medium", "low"],
                                         index=["high", "medium", "low"].index(prio),
                                         format_func=lambda p: f"{p.capitalize()}" + (" (model)" if p == prio else ""))
                    rules = matching_rules(final)
                    if c2.button("Create ticket", type="primary", icon=":material/add:", width="stretch", key="tr-create"):
                        res = create_ticket(draft["subject"] or draft["body"][:80], draft["body"] or draft["subject"],
                                            pred, requester=draft["requester"] or None, actor=actor,
                                            final_priority=final)
                        tid = res["ticket_id"]
                        st.session_state["triage_saved"] = {**res, "priority": final}
                        st.toast(f"Ticket #{tid} created.", icon=":material/check_circle:")
                        st.rerun()
                    if rules:
                        st.caption("On save: " + "; ".join(
                            f"{'creates' if r['mode'] == 'auto' else 'suggests'} “{r['action']}” "
                            f"(due in {r['sla_hours']} h)" for r in rules))
                else:
                    st.success(f"Saved as ticket #{saved['ticket_id']} with {saved['priority']} priority.",
                               icon=":material/check_circle:")
                    if saved["created"]:
                        st.markdown(f"Automation created {len(saved['created'])} task"
                                    f"{'s' if len(saved['created']) != 1 else ''}.")
                    for r in saved["suggestions"]:
                        a, b = st.columns([3, 1.2], vertical_alignment="center")
                        a.markdown(f"Suggested: **{r['action']}** :gray[({r['assignee'] or 'unassigned'}, "
                                   f"due in {r['sla_hours']} h)]")
                        if b.button("Create task", key=f"sugg-{r['id']}", width="stretch"):
                            task_from_rule(r, saved["ticket_id"], draft["subject"], actor, source="suggested")
                            saved["suggestions"] = [s for s in saved["suggestions"] if s["id"] != r["id"]]
                            st.toast("Task created.", icon=":material/task_alt:")
                            st.rerun()
                    b1, b2 = st.columns(2)
                    if b1.button("Triage another ticket", icon=":material/refresh:", width="stretch", key="tr-another"):
                        st.session_state.pop("triage_draft", None)
                        st.session_state.pop("triage_saved", None)
                        st.rerun()
                    if b2.button("View tasks", icon=":material/account_tree:", width="stretch", key="tr-view-tasks"):
                        st.switch_page(P["automation"])

            if pred.get("similar"):
                with st.container(key="card-similar"):
                    st.markdown("##### Similar resolved tickets")
                    for s in pred["similar"]:
                        prio_html = ui.priority_badge(s.get("priority"), prefix="Archive: ") if s.get("priority") else ""
                        st.markdown(f"**#{s['ticket_id']}** {prio_html} <span class='pg-muted'>similarity "
                                    f"{s['similarity']:.2f}</span><br>{ui.esc(ui.clip(s['snippet'], 200))}",
                                    unsafe_allow_html=True)
                        if s["answer"]:
                            with st.expander("Answer given" + (" (close match, reusable)" if s["similarity"] >= SIM_THRESHOLD else "")):
                                st.write(s["answer"])
            elif pred.get("similar_error"):
                st.warning("Similar-ticket search is unavailable: " + pred["similar_error"], icon=":material/warning:")

# ---------------------------------------------------------------- history
with tab_hist:
    f1, f0, f2, f3, f4 = st.columns([2, 1.2, 1, 1, 1.1], vertical_alignment="bottom")
    q = f1.text_input("Search tickets", placeholder="Subject, text or #id", key="hist_q")
    stage_opts = {"all": "All stages", "escalated": "New / escalated", "waiting": "Waiting on employee",
                  "self_resolved": "Self-resolved",
                  "assigned": "Assigned", "active": "All active"}
    if st.session_state.get("hist_stage") not in stage_opts:
        st.session_state.pop("hist_stage", None)
    fq = f0.selectbox("Stage", list(stage_opts), format_func=stage_opts.get, key="hist_stage")
    fs = f2.selectbox("Status", ["All", *STATUSES], format_func=lambda s: ui.STATUS_LABELS.get(s, s), key="hist_status")
    fp = f3.selectbox("Priority", ["All", "high", "medium", "low"], format_func=lambda s: s.capitalize(), key="hist_prio")
    arch = f4.toggle("Include archive", value=False, key="hist_arch",
                     help="Historical tickets imported from the knowledge base archive")
    rows = list_tickets(status=None if fs == "All" else fs, priority=None if fp == "All" else fp,
                        q=q or None, include_archive=arch, queue=None if fq == "all" else fq)
    if focus and focus not in [r["id"] for r in rows]:
        ft = get_ticket(focus)
        rows = ([ft] if ft else []) + rows
    if not rows:
        with st.container(key="card-hist-empty"):
            any_tickets = bool(list_tickets(include_archive=True, limit=1))
            ui.empty_state("search_off" if any_tickets else "inbox",
                           "No tickets match these filters" if any_tickets else "No tickets yet",
                           "Try clearing the search or filters." if any_tickets else
                           "Analyze and save a ticket on the New ticket tab and it appears here.")
    else:
        df = pd.DataFrame([{
            "id": r["id"], "subject": r["subject"], "priority": r["priority"].capitalize() if r["priority"] else "",
            "model": (r["predicted_priority"] or "").capitalize(), "confidence": round(100 * (r["confidence"] or 0)),
            "corrected": "Yes" if r["corrected"] else "", "stage": r["stage_label"],
            "requester": r.get("requester_name") or r.get("requester") or "",
            "assignee": r.get("assignee_name") or "", "source": r["source"], "created": ui.local_time(r["created_at"]),
        } for r in rows])
        ids = df["id"].tolist()
        default_rows = [ids.index(focus)] if focus in ids else []
        event = st.dataframe(
            df, hide_index=True, width="stretch", height=min(420, 38 + 35 * len(df)),
            on_select="rerun", selection_mode="single-row", key="hist_table",
            selection_default={"selection": {"rows": default_rows}} if default_rows else None,
            column_config={
                "id": st.column_config.NumberColumn("#", format="%d", width="small"),
                "subject": st.column_config.TextColumn("Subject", width="large"),
                "priority": st.column_config.TextColumn("Priority", width="small"),
                "model": st.column_config.TextColumn("Model said", width="small"),
                "confidence": st.column_config.ProgressColumn("Confidence", min_value=0, max_value=100,
                                                              format="%d%%"),
                "corrected": st.column_config.TextColumn("Corrected", width="small"),
                "stage": st.column_config.TextColumn("Stage", width="small"),
                "requester": st.column_config.TextColumn("Raised by", width="small"),
                "assignee": st.column_config.TextColumn("Assigned to", width="small"),
                "source": st.column_config.TextColumn("Source", width="small"),
                "created": st.column_config.TextColumn("Created"),
            },
        )
        sel = event.selection.rows if event and event.selection else []
        sel_id = ids[sel[0]] if sel else (focus if focus in ids else None)
        if sel_id is None:
            st.caption(f"{len(rows)} ticket{'s' if len(rows) != 1 else ''}. Select a row to review, change its "
                       "status or correct its priority.")
        else:
            t = get_ticket(sel_id)
            with st.container(key="card-ticket"):
                h1, h2 = st.columns([3, 1.4])
                h1.markdown(f"#### #{t['id']} {ui.esc(t['subject'])}", unsafe_allow_html=True)
                h1.markdown(
                    f"{ui.priority_badge(t['priority'])} {ui.stage_badge(t['stage'])} "
                    f"{ui.soft_badge('Archive ticket') if t['source'] == 'archive' else ''} "
                    f"<span class='pg-muted'>Created {ui.esc(ui.local_time(t['created_at']))}"
                    f"{' by ' + ui.esc(t['requester_name'] or t['created_by']) if (t['requester_name'] or t['created_by']) else ''}"
                    f"{' · assigned to ' + ui.esc(t['assignee_name']) if t.get('assignee_name') else ''}</span>",
                    unsafe_allow_html=True)
                with h2:
                    probs = {"low": t["prob_low"] or 0, "medium": t["prob_medium"] or 0, "high": t["prob_high"] or 0}
                    st.markdown(ui.prob_meter(probs, t["predicted_priority"]), unsafe_allow_html=True)
                st.write(t["body"])
                if t["corrected"]:
                    st.info(f"Model predicted {t['predicted_priority']}; corrected to {t['final_priority']} by "
                            f"{t['corrected_by'] or 'an agent'} ({ui.local_time(t['corrected_at'])}).",
                            icon=":material/edit:")
                if t.get("reference_priority"):
                    st.caption(f"Original dataset label: {t['reference_priority']}. Archive tickets were part of the "
                               "model's training data.")
                c1, c2, c3 = st.columns(3, vertical_alignment="bottom")
                new_status = c1.selectbox("Status", STATUSES, index=STATUSES.index(t["status"]),
                                          format_func=lambda s: ui.STATUS_LABELS[s], key=f"st-{t['id']}")
                new_prio = c2.selectbox("Priority", ["high", "medium", "low"],
                                        index=["high", "medium", "low"].index(t["priority"]),
                                        format_func=lambda p: p.capitalize() + (" (model)" if p == t["predicted_priority"] else ""),
                                        key=f"pr-{t['id']}")
                if c3.button("Save changes", type="primary", key=f"save-{t['id']}", width="stretch",
                             disabled=(new_status == t["status"] and new_prio == t["priority"])):
                    if new_status != t["status"]:
                        set_status(t["id"], new_status, actor=actor)
                    if new_prio != t["priority"]:
                        correct_priority(t["id"], new_prio, actor=actor)
                    st.session_state["focus_ticket"] = t["id"]
                    st.toast("Ticket updated.", icon=":material/check_circle:")
                    st.rerun()
                if t["source"] != "archive":
                    st.markdown("**Workflow**")
                    st.markdown(ui.progress_steps(t), unsafe_allow_html=True)
                    if t["stage"] == "suggested":
                        st.markdown(f"Recommended solution from resolved ticket #{t['match_ticket_id']} "
                                    f"({t['match_similarity']:.0%} similar):")
                        if t.get("requester_account_id"):
                            st.markdown(f'<div class="pg-solution">{ui.esc(t["suggested_solution"] or "")}</div>',
                                        unsafe_allow_html=True)
                            st.caption(f"{t.get('requester_name') or 'The employee'} was given this solution and will "
                                       "close the ticket if it works or escalate it. No approval needed.")
                        else:  # triaged here by an analyst: nobody else will confirm it
                            sol = st.text_area("Recommended solution", value=t["suggested_solution"] or "", height=140,
                                               key=f"tr-sol-{t['id']}", label_visibility="collapsed")
                            w1, w2, _ = st.columns([1.3, 1, 1.4])
                            if w1.button("Resolve with this", type="primary", key=f"tr-ok-{t['id']}", width="stretch",
                                         icon=":material/check:"):
                                try:
                                    approve_suggestion(t["id"], user, sol)
                                except ValueError as e:
                                    st.error(str(e), icon=":material/error:")
                                else:
                                    st.session_state["focus_ticket"] = t["id"]
                                    st.toast("Ticket resolved with the recommended solution.",
                                             icon=":material/check_circle:")
                                    st.rerun()
                            if w2.button("Doesn't fit", key=f"tr-no-{t['id']}", width="stretch",
                                         icon=":material/close:"):
                                reject_suggestion(t["id"], user)
                                st.session_state["focus_ticket"] = t["id"]
                                st.rerun()
                    elif t.get("review_status") == "self_resolved":
                        st.success("Closed by the employee with a recommended solution (self-service).",
                                   icon=":material/task_alt:")
                    if t["status"] in ("open", "in_progress"):
                        people = list_accounts(active_only=True)
                        opts = [None] + [a["id"] for a in people]
                        names = {a["id"]: f"{a['name']} ({a['login_id']}) · {a['role_label']}" for a in people}
                        cur = t.get("assignee_account_id")
                        a1, a2 = st.columns([3, 1], vertical_alignment="bottom")
                        who = a1.selectbox("Assigned to", opts, index=opts.index(cur) if cur in opts else 0,
                                           format_func=lambda i: names.get(i, "Unassigned"), key=f"tr-who-{t['id']}")
                        if a2.button("Update", key=f"tr-assign-{t['id']}", width="stretch", disabled=who == cur):
                            assign_ticket(t["id"], who, user)
                            st.session_state["focus_ticket"] = t["id"]
                            st.toast("Assignment updated.", icon=":material/assignment_ind:")
                            st.rerun()
                        with st.form(f"tr-res-{t['id']}", border=False):
                            res_text = st.text_area("Resolve with a solution", height=100,
                                                    placeholder="Sent to the employee and added to the knowledge base.")
                            if st.form_submit_button("Resolve ticket", icon=":material/task_alt:"):
                                try:
                                    resolve_ticket(t["id"], res_text, user)
                                except (ValueError, PermissionDenied) as e:
                                    st.error(str(e), icon=":material/error:")
                                else:
                                    st.session_state["focus_ticket"] = t["id"]
                                    st.toast("Ticket resolved.", icon=":material/task_alt:")
                                    st.rerun()
                    elif t.get("resolution"):
                        st.markdown(f'<div class="pg-solution">{ui.esc(t["resolution"])}</div>', unsafe_allow_html=True)
                        st.caption(f"Resolved by {t.get('resolved_by') or 'the team'} {ui.ago(t.get('resolved_at'))}")
                        if st.button("Reopen", key=f"tr-reopen-{t['id']}", icon=":material/replay:"):
                            reopen_ticket(t["id"], user)
                            st.session_state["focus_ticket"] = t["id"]
                            st.rerun()
                    with st.expander("Timeline", icon=":material/history:"):
                        ev = ticket_timeline(t["id"])
                        if ev:
                            ui.activity_feed(list(reversed(ev)))
                        else:
                            st.caption("No recorded events.")
                tasks = list_tasks(ticket_id=t["id"])
                st.markdown("**Tasks for this ticket**")
                if not tasks:
                    st.caption("No tasks yet.")
                for k in tasks:
                    due = f", due {ui.ago(k['due_at'])}" if k["due_at"] and k["status"] != "done" else ""
                    flag = " :red-badge[Overdue]" if k["overdue"] else ""
                    st.markdown(f"- {k['title']} :gray[({ui.STATUS_LABELS[k['status']]}, "
                                f"{k['assignee'] or 'unassigned'}{due})]{flag}")
                with st.popover("Add a task", icon=":material/add_task:"):
                    with st.form(f"task-{t['id']}", border=False):
                        title = st.text_input("Task")
                        assignee = st.text_input("Assignee")
                        hours = st.number_input("Due in (hours)", min_value=1, max_value=720, value=24)
                        if st.form_submit_button("Create task", type="primary"):
                            if title.strip():
                                create_task(title, description=f"Ticket #{t['id']}: {t['subject']}", ticket_id=t["id"],
                                            priority=t["priority"], assignee=assignee or None, due_in_hours=hours,
                                            created_by=actor)
                                st.session_state["focus_ticket"] = t["id"]
                                st.rerun()
                            else:
                                st.error("Give the task a title.")
