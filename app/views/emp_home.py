"""Employee home: welcome, ticket tracking, quick actions and solution recommendations."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import ui  # noqa: E402
from copilot.triage import TriageUnavailable, find_solutions, list_tickets, my_ticket_counts, self_resolve  # noqa: E402

user = ui.require_role("employee")
first = user["name"].split(" ")[0]
hour = datetime.now().hour
greet = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Good evening")
ui.page_header(f"{greet}, {first}", "Your enterprise workspace: raise support tickets, track their progress and "
               "find answers that already exist.")

c = my_ticket_counts(user["id"])
k1, k2, k3, k4 = st.columns(4)
with k1:
    ui.kpi("Active tickets", f"{c['active']}", f"{c['total']} raised in total" if c["total"] else "None raised yet",
           icon_name="confirmation_number")
with k2:
    ui.kpi("Solution suggested", f"{c['suggested']}", "Try it, then close or escalate", icon_name="lightbulb",
           tone=ui.STAGE_COLORS["suggested"] if c["suggested"] else None)
with k3:
    ui.kpi("With the support team", f"{c['escalated'] + c['in_progress']}",
           f"{c['escalated']} escalated, {c['in_progress']} assigned or in progress", icon_name="support_agent")
with k4:
    ui.kpi("Resolved", f"{c['resolved']}", "Solved or closed", icon_name="task_alt",
           tone=ui.STAGE_COLORS["resolved"] if c["resolved"] else None)

if c["assigned_to_me"]:
    st.write("")
    with st.container(key="card-assigned-banner"):
        a, b = st.columns([4, 1.2], vertical_alignment="center")
        a.markdown(f"**{c['assigned_to_me']} ticket{'s are' if c['assigned_to_me'] != 1 else ' is'} assigned to you.** "
                   "<span class='pg-muted'>A Senior Analyst asked you to work on "
                   f"{'them' if c['assigned_to_me'] != 1 else 'it'}.</span>", unsafe_allow_html=True)
        if b.button("Open assigned tickets", type="primary", key="home-assigned", width="stretch"):
            st.session_state["emp_tab"] = "assigned"
            ui.go("my_tickets")

st.write("")
a1, a2, a3 = st.columns(3)
with a1, st.container(key="action-submit"):
    if st.button("Submit a new support ticket", icon=":material/add_circle:", type="primary", width="stretch",
                 key="home-submit"):
        ui.go("submit")
with a2, st.container(key="action-ask"):
    if st.button("Ask the AI assistant", icon=":material/forum:", width="stretch", key="home-ask"):
        ui.go("assistant")
with a3, st.container(key="action-kb"):
    if st.button("Browse the Knowledge Hub", icon=":material/library_books:", width="stretch", key="home-kb"):
        ui.go("knowledge")

st.write("")
left, right = st.columns([1.35, 1], gap="medium")
with left:
    with st.container(key="card-my-recent"):
        st.markdown("##### My tickets")
        mine = list_tickets(requester_account_id=user["id"], limit=6)
        if not mine:
            ui.empty_state("confirmation_number", "No tickets yet",
                           "When something isn't working, submit a ticket. You can follow every step here.")
        for t in mine[:5]:
            a, b = st.columns([5, 1], vertical_alignment="center")
            a.markdown(f"{ui.stage_badge(t['stage'])} {ui.priority_badge(t['priority'])} &nbsp;**#{t['id']}** "
                       f"{ui.esc(ui.clip(t['subject'], 70))}<br><span class='pg-muted'>Raised {ui.ago(t['created_at'])}"
                       f"{', with ' + ui.esc(t['assignee_name']) if t.get('assignee_name') else ''}</span>",
                       unsafe_allow_html=True)
            if b.button("View", key=f"home-t-{t['id']}", type="tertiary"):
                st.session_state["focus_ticket"] = t["id"]
                st.session_state["emp_tab"] = "mine"
                ui.go("my_tickets")
            st.markdown(ui.progress_steps(t), unsafe_allow_html=True)
        if len(mine) > 5 and st.button("See all my tickets", type="tertiary", key="home-all"):
            ui.go("my_tickets")

    solved = [t for t in list_tickets(requester_account_id=user["id"], limit=50)
              if t["status"] in ("resolved", "closed") and t.get("resolution")][:3]
    if solved:
        with st.container(key="card-my-solutions"):
            st.markdown("##### Solutions for your tickets")
            for t in solved:
                st.markdown(f"**#{t['id']} {ui.esc(ui.clip(t['subject'], 80))}** "
                            f"<span class='pg-muted'>· resolved {ui.ago(t.get('resolved_at') or t['updated_at'])}</span>",
                            unsafe_allow_html=True)
                st.markdown(f'<div class="pg-solution">{ui.esc(ui.clip(t["resolution"], 400))}</div>',
                            unsafe_allow_html=True)
                st.write("")

with right:
    with st.container(key="card-recommend"):
        st.markdown("##### Existing solution recommendations")
        st.caption("Describe a problem to see how similar tickets were solved before, and matching company "
                   "documents. Often you won't need to raise a ticket at all.")
        with st.form("home-find", border=False):
            q = st.text_input("Describe the problem", placeholder="e.g. VPN disconnects every few minutes",
                              label_visibility="collapsed")
            go = st.form_submit_button("Find solutions", icon=":material/lightbulb:", width="stretch")
        if go and q.strip():
            with st.spinner("Searching resolved tickets and documents…"):
                st.session_state["home_solutions"] = (q.strip(), find_solutions(q.strip()))
        found = st.session_state.get("home_solutions")
        if found:
            st.markdown(f"<span class='pg-muted'>Results for “{ui.esc(found[0])}”</span>", unsafe_allow_html=True)
            n, picked = ui.solution_cards(found[1], "home", pick_label="This solved my problem")
            if not n:
                st.info("No close match among resolved tickets or documents. Submit a ticket and the support team "
                        "will take it from there.", icon=":material/info:")
            if picked:
                try:
                    with st.spinner("Recording the solved issue…"):
                        t = self_resolve(found[0], found[0], picked, user)
                except (ValueError, TriageUnavailable) as e:
                    st.error(str(e), icon=":material/error:")
                else:
                    st.session_state.pop("home_solutions", None)
                    st.session_state["_toast"] = (f"Recorded as ticket #{t['id']} and closed as solved. The Senior "
                                                  "Analysts see it as completed; nothing was escalated.")
                    st.rerun()
