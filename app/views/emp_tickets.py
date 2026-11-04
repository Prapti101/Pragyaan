"""Employee: my tickets (raised by me) and tickets assigned to me, with progress tracking."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import ui  # noqa: E402
from copilot.auth import PermissionDenied  # noqa: E402
from copilot.triage import (accept_suggestion, close_ticket, confirm_resolved, decline_suggestion,  # noqa: E402
                            get_ticket_for, list_tickets, reopen_ticket,
                            resolve_ticket, start_work, ticket_timeline)

user = ui.require_role("employee")
ui.page_header("My tickets", "Follow your tickets from submission to resolution, and work on tickets assigned to you.")

mine = list_tickets(requester_account_id=user["id"])
assigned = list_tickets(assignee_account_id=user["id"])

focus = st.session_state.pop("focus_ticket", None)
if focus and any(t["id"] == focus for t in assigned) and not any(t["id"] == focus for t in mine):
    st.session_state["emp_tab"] = "assigned"
tab_opts = {"mine": f"Raised by me ({len(mine)})", "assigned": f"Assigned to me ({len(assigned)})"}
st.session_state.setdefault("emp_tab", "mine")
tab = st.segmented_control("View", list(tab_opts), format_func=tab_opts.get, key="emp_tab", required=True,
                           label_visibility="collapsed") or "mine"
rows = mine if tab == "mine" else assigned

f1, f2 = st.columns([1, 2])
show = f1.selectbox("Show", ["All", "Active", "Resolved"], key="emp_filter", label_visibility="collapsed")
q = f2.text_input("Filter", placeholder="Filter by words or #number", key="emp_q", label_visibility="collapsed",
                  icon=":material/filter_list:")
if show == "Active":
    rows = [t for t in rows if t["status"] in ("open", "in_progress")]
elif show == "Resolved":
    rows = [t for t in rows if t["status"] in ("resolved", "closed")]
# what needs attention first: in review / escalated / in progress, then resolved (awaiting your confirmation), then closed
rows = sorted(rows, key=lambda t: ({"closed": 2, "resolved": 1}.get(t["status"], 0), -t["id"]))
if q.strip():
    needle = q.strip().lower().lstrip("#")
    rows = [t for t in rows if needle == str(t["id"]) or needle in f"{t['subject']} {t['body']}".lower()]

if not rows:
    if tab == "mine":
        ui.empty_state("confirmation_number", "No tickets here",
                       "Tickets you raise appear here with their priority and progress." if not mine
                       else "No ticket matches this filter.")
        if not mine and st.button("Submit a ticket", type="primary", icon=":material/add_circle:", key="mt-new"):
            ui.go("submit")
    else:
        ui.empty_state("assignment_ind", "Nothing assigned to you",
                       "When a Senior Analyst assigns you a ticket, it shows up here.")
    st.stop()

ids = [t["id"] for t in rows]
sel_key = f"emp_sel_{tab}"
if focus in ids:
    st.session_state[sel_key] = focus
if st.session_state.get(sel_key) not in ids:
    st.session_state[sel_key] = ids[0]

left, right = st.columns([1, 1.45], gap="medium")
with left:
    with st.container(key="card-mt-list", height=640):
        for t in rows:
            active = t["id"] == st.session_state[sel_key]
            st.markdown(f"{ui.stage_badge(t['stage'])} {ui.priority_badge(t['priority'])}", unsafe_allow_html=True)
            if st.button(f"#{t['id']} · {ui.clip(t['subject'], 60)}", key=f"mt-pick-{tab}-{t['id']}",
                         type="primary" if active else "tertiary", width="stretch"):
                st.session_state[sel_key] = t["id"]
                st.rerun()
            st.caption(f"Raised {ui.ago(t['created_at'])}" + (f" by {t['requester_name']}" if tab == "assigned" and
                                                               t.get("requester_name") else ""))

with right:
    try:
        t = get_ticket_for(st.session_state[sel_key], user)
    except PermissionDenied as e:
        st.error(str(e), icon=":material/lock:")
        st.stop()
    with st.container(key="card-mt-detail"):
        st.markdown(f"#### #{t['id']} {ui.esc(t['subject'])}", unsafe_allow_html=True)
        st.markdown(f"{ui.stage_badge(t['stage'])} {ui.priority_badge(t['priority'])} &nbsp;<span class='pg-muted'>"
                    f"Raised {ui.local_time(t['created_at'])} · updated {ui.ago(t['updated_at'])}</span>",
                    unsafe_allow_html=True)
        st.markdown(ui.progress_steps(t), unsafe_allow_html=True)
        st.markdown(ui.md_lines(t["body"]))
        info = [f"**Priority** {t['priority']} (model {t['predicted_priority']}, {t['confidence']:.0%} confident"
                f"{'; adjusted by a Senior Analyst' if t['corrected'] else ''})" if t.get("confidence") is not None
                else f"**Priority** {t['priority']}"]
        if t.get("assignee_name"):
            info.append(f"**Handled by** {t['assignee_name']}")
        if tab == "assigned" and t.get("requester_name"):
            info.append(f"**Raised by** {t['requester_name']} ({t['requester_login']})")
        st.markdown("  \n".join(info))

        if t["stage"] == "suggested":
            st.markdown(f"**Recommended solution** <span class='pg-muted'>from resolved ticket #{t['match_ticket_id']}"
                        f" · {t['match_similarity']:.0%} similar</span>", unsafe_allow_html=True)
            st.markdown(f'<div class="pg-solution">{ui.esc(t["suggested_solution"] or "")}</div>',
                        unsafe_allow_html=True)
            if tab == "mine":
                st.caption("Did it fix the problem? Close the ticket, or send it to a Senior Analyst.")
                a, b = st.columns(2)
                if a.button("This solved my issue", type="primary", icon=":material/check_circle:",
                            key=f"mt-accept-{t['id']}", width="stretch"):
                    accept_suggestion(t["id"], user)
                    st.toast("Ticket closed as solved. Thanks!", icon=":material/check_circle:")
                    st.rerun()
                with b.popover("Not solved, escalate", icon=":material/support_agent:", width="stretch"):
                    why = st.text_area("What didn't work? (optional)", key=f"mt-decline-why-{t['id']}", height=90)
                    if st.button("Escalate to a Senior Analyst", key=f"mt-decline-{t['id']}", type="primary",
                                 width="stretch"):
                        decline_suggestion(t["id"], user, why)
                        st.toast("Escalated to the Senior Analysts.", icon=":material/support_agent:")
                        st.rerun()
        elif t["stage"] == "escalated":
            st.info("A Senior Analyst will handle this ticket: " + (
                "you said the recommended solution didn't help." if t.get("review_status") == "declined" else
                "there was no close match among resolved tickets."), icon=":material/support_agent:")

        if t.get("resolution"):
            self_service = t.get("review_status") == "self_resolved"
            st.markdown("**Solution that worked**" if self_service else "**Solution**")
            st.markdown(f'<div class="pg-solution">{ui.esc(t["resolution"])}</div>', unsafe_allow_html=True)
            if self_service:
                st.caption(f"Closed by you {ui.ago(t.get('resolved_at'))} using a recommended solution. The Senior "
                           "Analysts see it as completed.")
            else:
                st.caption(f"Resolved by {t.get('resolved_by') or 'the support team'} {ui.ago(t.get('resolved_at'))}")

        # an open ticket can be closed by the person who raised it once the issue is solved
        if tab == "mine" and t["status"] in ("open", "in_progress") and t["stage"] != "suggested":
            with st.popover("My issue is solved, close ticket", icon=":material/task_alt:"):
                note = st.text_area("What solved it? (optional)", key=f"mt-close-note-{t['id']}", height=90)
                if st.button("Close ticket", key=f"mt-close-{t['id']}", type="primary", width="stretch"):
                    close_ticket(t["id"], user, note)
                    st.toast("Ticket closed.", icon=":material/task_alt:")
                    st.rerun()

        # --- actions for the person who raised the ticket
        if tab == "mine" and t["status"] == "resolved":
            st.write("")
            a, b = st.columns(2)
            if a.button("This solved my issue", type="primary", icon=":material/check_circle:", key=f"mt-ok-{t['id']}",
                        width="stretch"):
                confirm_resolved(t["id"], user)
                st.toast("Thanks! The ticket is closed.", icon=":material/check_circle:")
                st.rerun()
            with b.popover("Still need help", icon=":material/replay:", width="stretch"):
                why = st.text_area("What's still wrong?", key=f"mt-why-{t['id']}", height=90)
                if st.button("Reopen ticket", key=f"mt-reopen-{t['id']}", type="primary", width="stretch"):
                    reopen_ticket(t["id"], user, why)
                    st.toast("Ticket reopened and sent back to the support team.", icon=":material/replay:")
                    st.rerun()
        elif tab == "mine" and t["status"] == "closed":
            with st.popover("Reopen", icon=":material/replay:"):
                why = st.text_area("What's wrong?", key=f"mt-why2-{t['id']}", height=90)
                if st.button("Reopen ticket", key=f"mt-reopen2-{t['id']}", type="primary"):
                    reopen_ticket(t["id"], user, why)
                    st.rerun()

        # --- actions for the assignee
        if tab == "assigned" and t["status"] in ("open", "in_progress"):
            st.divider()
            st.markdown("**Work on this ticket**")
            if t["status"] == "open" and st.button("Start work", icon=":material/play_arrow:", key=f"mt-start-{t['id']}"):
                start_work(t["id"], user)
                st.toast(f"Ticket #{t['id']} is in progress.", icon=":material/play_arrow:")
                st.rerun()
            with st.form(f"mt-resolve-{t['id']}", border=False):
                text = st.text_area("Solution", height=120, placeholder="What fixed it? This is sent to the employee "
                                    "and added to the knowledge base for similar tickets.")
                ok = st.form_submit_button("Resolve ticket", type="primary", icon=":material/task_alt:")
            if ok:
                try:
                    with st.spinner("Saving the solution and updating the knowledge base…"):
                        resolve_ticket(t["id"], text, user)
                except (ValueError, PermissionDenied) as e:
                    st.error(str(e), icon=":material/error:")
                else:
                    st.toast(f"Ticket #{t['id']} resolved.", icon=":material/task_alt:")
                    st.rerun()

    with st.container(key="card-mt-timeline"):
        st.markdown("##### Timeline")
        events = ticket_timeline(t["id"])
        if events:
            ui.activity_feed(list(reversed(events)))
        else:
            st.caption("No updates yet.")
