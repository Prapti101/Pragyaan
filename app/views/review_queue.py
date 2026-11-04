"""Senior Analyst: work the New / Escalated queue, assign tickets, and see what employees solved themselves."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import ui  # noqa: E402
from copilot.auth import PermissionDenied, list_accounts  # noqa: E402
from copilot.triage import (assign_ticket, correct_priority, list_tickets, queue_counts,  # noqa: E402
                            reopen_ticket, resolve_ticket, self_service_stats, workload)

user = ui.require_role("analyst")
ui.page_header("Escalations",
               "Tickets that need a Senior Analyst: no close match among resolved tickets, or the employee said the "
               "recommended solution didn't help. Tickets employees solved themselves are listed for reference.")

qc = queue_counts()
ss = self_service_stats()
k1, k2, k3, k4 = st.columns(4)
with k1:
    ui.kpi("New / escalated", f"{qc['escalated']}", "Need an owner or an answer", icon_name="priority_high",
           tone=ui.STAGE_COLORS["escalated"] if qc["escalated"] else None)
with k2:
    ui.kpi("Assigned", f"{qc['assigned']}", "Open or in progress with a team member", icon_name="assignment_ind")
with k3:
    ui.kpi("Waiting on employee", f"{qc['waiting']}", "Trying a recommended solution", icon_name="hourglass_top",
           tone=ui.STAGE_COLORS["suggested"] if qc["waiting"] else None)
with k4:
    rate = f", {ss['rate_pct']:.0f}% of employee tickets" if ss["rate_pct"] is not None else ""
    ui.kpi("Self-resolved", f"{ss['total']}", f"{ss['recent']} in the last 7 days{rate}", icon_name="task_alt",
           tone=ui.STAGE_COLORS["resolved"] if ss["total"] else None)
st.write("")

people = [a for a in list_accounts(active_only=True)]
load = {w["id"]: w for w in workload()}


def person_label(aid: int | None) -> str:
    if aid is None:
        return "Choose a team member…"
    a = next(p for p in people if p["id"] == aid)
    w = load.get(aid, {})
    return f"{a['name']} ({a['login_id']}) · {a['role_label']} · {int(w.get('active') or 0)} active"


def assign_box(t: dict, key: str) -> None:
    opts = [None] + [p["id"] for p in people]
    cur = t.get("assignee_account_id")
    a, b = st.columns([3, 1], vertical_alignment="bottom")
    choice = a.selectbox("Assign to", opts, index=opts.index(cur) if cur in opts else 0, format_func=person_label,
                         key=f"{key}-who-{t['id']}")
    if b.button("Assign", key=f"{key}-assign-{t['id']}", width="stretch", disabled=choice is None or choice == cur,
                icon=":material/assignment_ind:"):
        try:
            assign_ticket(t["id"], choice, user)
        except (ValueError, PermissionDenied) as e:
            st.error(str(e), icon=":material/error:")
        else:
            st.toast(f"Ticket #{t['id']} assigned.", icon=":material/assignment_ind:")
            st.rerun()


def ticket_head(t: dict) -> None:
    st.markdown(f"{ui.priority_badge(t['priority'])} {ui.stage_badge(t['stage'])} &nbsp;**#{t['id']} "
                f"{ui.esc(ui.clip(t['subject'], 110))}**", unsafe_allow_html=True)
    who = t.get("requester_name") or t.get("requester") or "unknown requester"
    conf = f", model {t['confidence']:.0%} confident" if t.get("confidence") is not None else ""
    st.markdown(f"<span class='pg-muted'>Raised by {ui.esc(who)} {ui.ago(t['created_at'])}{conf}"
                f"{'; priority adjusted' if t['corrected'] else ''}</span>", unsafe_allow_html=True)


def priority_box(t: dict, key: str) -> None:
    cur = t["priority"]
    new = st.segmented_control("Priority", ["low", "medium", "high"], default=cur, format_func=str.capitalize,
                               key=f"{key}-prio-{t['id']}", required=True)
    if new and new != cur:
        correct_priority(t["id"], new, actor=user["login_id"])
        st.toast(f"Ticket #{t['id']} set to {new}.", icon=":material/edit:")
        st.rerun()


def by_urgency(rows: list[dict]) -> list[dict]:
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(rows, key=lambda t: (order.get(t["priority"], 3), t["id"]))


tabs = {"escalated": f"New / escalated ({qc['escalated']})", "assigned": f"Assigned ({qc['assigned']})",
        "waiting": f"Waiting on employee ({qc['waiting']})", "self_resolved": f"Self-resolved ({qc['self_resolved']})"}
focus = st.session_state.pop("focus_ticket", None)
if focus:
    for name in tabs:
        if any(t["id"] == focus for t in list_tickets(queue=name)):
            st.session_state["rq_tab"] = name
if st.session_state.get("rq_tab") not in tabs:
    st.session_state["rq_tab"] = "escalated"
tab = st.segmented_control("Queue", list(tabs), format_func=tabs.get, key="rq_tab", required=True,
                           label_visibility="collapsed") or "escalated"
rows = list_tickets(queue=tab) if tab == "self_resolved" else by_urgency(list_tickets(queue=tab))
if focus in [t["id"] for t in rows]:
    rows = [t for t in rows if t["id"] == focus] + [t for t in rows if t["id"] != focus]

if not rows:
    msg = {"escalated": ("inbox", "No escalated tickets",
                         "Tickets with no close match, or whose recommended solution didn't help, appear here until "
                         "someone is assigned."),
           "assigned": ("assignment_ind", "Nothing assigned", "Tickets you assign to team members appear here."),
           "waiting": ("hourglass_top", "Nobody is trying a recommended solution right now",
                       "When a ticket closely matches a resolved one, the employee gets its solution straight away "
                       "and appears here until they close or escalate it."),
           "self_resolved": ("task_alt", "No self-resolved tickets yet",
                             "Tickets employees close with a recommended solution are listed here. No action needed.")}[tab]
    ui.empty_state(*msg)
    st.stop()

if tab == "self_resolved":
    st.caption("Completed by employees with a recommended solution. Nothing to do here; reopen one if the solution "
               "looks wrong and it will move to escalated tickets.")
    for t in rows[:st.session_state.get("rq_limit", 10)]:
        with st.container(key=f"card-rq-sr-{t['id']}"):
            a, b = st.columns([5, 1], vertical_alignment="top")
            with a:
                ticket_head(t)
                src = (f"resolved ticket #{t['match_ticket_id']}" if t.get("match_ticket_id") else "the Knowledge Hub")
                sim = f", {t['match_similarity']:.0%} similar" if t.get("match_similarity") else ""
                st.markdown(f"<span class='pg-muted'>Solved {ui.ago(t.get('resolved_at'))} with the solution from "
                            f"{src}{sim}</span>", unsafe_allow_html=True)
                with st.expander("Problem and solution used"):
                    st.markdown(ui.md_lines(ui.clip(t["body"], 600)))
                    st.markdown(f'<div class="pg-solution">{ui.esc(ui.clip(t["resolution"] or "", 900))}</div>',
                                unsafe_allow_html=True)
            if b.button("Reopen", key=f"sr-reopen-{t['id']}", icon=":material/replay:", width="stretch"):
                reopen_ticket(t["id"], user, "reopened by a Senior Analyst after review")
                st.toast(f"Ticket #{t['id']} moved to escalated tickets.", icon=":material/replay:")
                st.rerun()
    if len(rows) > st.session_state.get("rq_limit", 10) and st.button("Show more", key="sr-more"):
        st.session_state["rq_limit"] = st.session_state.get("rq_limit", 10) + 10
        st.rerun()
    st.stop()

limit = st.session_state.get("rq_limit", 10)
for t in rows[:limit]:
    with st.container(key=f"card-rq-{tab}-{t['id']}"):
        ticket_head(t)
        left, right = st.columns([1, 1.15], gap="large")
        with left:
            st.markdown(ui.md_lines(ui.clip(t["body"], 900)))
            if t.get("reason_terms"):
                st.caption("Words that drove the priority: " + ", ".join(t["reason_terms"][:6]))
            if t.get("review_status") == "declined" and t.get("suggested_solution"):
                st.warning(f"The employee tried the recommended solution from resolved ticket #{t['match_ticket_id']} "
                           f"({t['match_similarity']:.0%} similar) and said it didn't help.", icon=":material/replay:")
                with st.expander("Recommended solution they tried"):
                    st.markdown(f'<div class="pg-solution">{ui.esc(t["suggested_solution"])}</div>',
                                unsafe_allow_html=True)
            elif t["stage"] == "suggested":
                st.info(f"The employee was given the solution from resolved ticket #{t['match_ticket_id']} "
                        f"({t['match_similarity']:.0%} similar) and hasn't said yet whether it worked. You can still "
                        "assign or resolve it.", icon=":material/hourglass_top:")
            elif t.get("review_status") == "rejected" and t.get("suggested_solution"):
                st.caption(f"A Senior Analyst set aside the recommended solution from ticket #{t['match_ticket_id']}.")
            priority_box(t, tab)
        with right:
            if tab == "assigned":
                st.markdown(f"**With** {ui.esc(t.get('assignee_name') or '')} "
                            f"<span class='pg-muted'>({ui.STATUS_LABELS[t['status']].lower()})</span>",
                            unsafe_allow_html=True)
            assign_box(t, tab)
            with st.form(f"{tab}-res-{t['id']}", border=False):
                sol = st.text_area("Or resolve it yourself", height=110, placeholder="Write the solution. The "
                                   "employee is notified and it's added to the knowledge base.")
                ok = st.form_submit_button("Resolve", type="primary", icon=":material/task_alt:")
            if ok:
                try:
                    with st.spinner("Resolving and updating the knowledge base…"):
                        resolve_ticket(t["id"], sol, user)
                except (ValueError, PermissionDenied) as e:
                    st.error(str(e), icon=":material/error:")
                else:
                    st.toast(f"Ticket #{t['id']} resolved.", icon=":material/task_alt:")
                    st.rerun()
if len(rows) > limit and st.button(f"Show {min(10, len(rows) - limit)} more", key="rq-more", icon=":material/expand_more:"):
    st.session_state["rq_limit"] = limit + 10
    st.rerun()
