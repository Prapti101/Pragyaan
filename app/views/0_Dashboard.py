"""Senior Analyst: enterprise operations overview (queues, priorities, tasks, team, activity)."""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import ui  # noqa: E402
from copilot.activity import recent_activity  # noqa: E402
from copilot.automation import list_tasks, task_stats  # noqa: E402
from copilot.db import fetchone  # noqa: E402
from copilot.escalation import list_open_escalations  # noqa: E402
from copilot.knowledge import list_documents  # noqa: E402
from copilot.auth import list_reset_requests  # noqa: E402
from copilot.triage import (daily_counts, import_archive_samples, list_tickets, queue_counts,  # noqa: E402
                            self_service_stats, ticket_stats, workload)

P = st.session_state["_pages"]
user = ui.require_role("analyst")

hour = datetime.now().hour
greet = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Good evening")
ui.page_header(f"{greet}, {user['name'].split(' ')[0]}",
               "Enterprise operations overview: what needs a decision, how priorities are spread and how the team "
               "is loaded.")
if "@" in user["login_id"]:
    st.info("Your sign-in ID is still your old e-mail address. Give yourself a Senior Analyst ID (e.g. SA-001) in "
            "Team management; you'll sign in with it from then on.", icon=":material/badge:")

ts = ticket_stats(include_archive=True)
ks = task_stats()
esc_open = list_open_escalations()
docs = list_documents()
week = fetchone("SELECT COUNT(*) AS n FROM tickets WHERE source = 'manual' AND created_at >= datetime('now', '-7 days')")
week_n = int(week["n"]) if week else 0

qc = queue_counts()
resets = list_reset_requests(user)
ss = self_service_stats()
q1, q2, q3, q4 = st.columns(4)
with q1:
    ui.kpi("New / escalated", f"{qc['escalated']}", "Need an owner or an answer", icon_name="priority_high",
           tone=ui.STAGE_COLORS["escalated"] if qc["escalated"] else None)
with q2:
    rate = f" · {ss['rate_pct']:.0f}% of employee tickets" if ss["rate_pct"] is not None else ""
    ui.kpi("Self-resolved by employees", f"{ss['total']}", f"{ss['recent']} this week{rate}", icon_name="task_alt",
           tone=ui.STAGE_COLORS["resolved"] if ss["total"] else None)
with q3:
    ui.kpi("Assigned & in progress", f"{qc['assigned']}", "With a team member", icon_name="assignment_ind")
with q4:
    ui.kpi("Senior Queue", f"{len(esc_open)}", "Assistant questions awaiting an answer", icon_name="support_agent",
           tone=ui.WARNING if esc_open else None)
if qc["escalated"] or resets:
    st.write("")
    with st.container(key="card-decisions"):
        a, b, c, d = st.columns([2.6, 1.2, 1.2, 1.2], vertical_alignment="center")
        parts = []
        if qc["escalated"]:
            parts.append(f"**{qc['escalated']}** escalated ticket{'s' if qc['escalated'] != 1 else ''} to assign")
        if resets:
            parts.append(f"**{len(resets)}** password reset request{'s' if len(resets) != 1 else ''}")
        a.markdown("Waiting for you: " + ", ".join(parts) + ".")
        if qc["escalated"] and b.button("Assign tickets", type="primary", key="dash-esc", width="stretch"):
            st.session_state["rq_tab"] = "escalated"
            st.switch_page(P["review"])
        if resets and c.button("Handle resets", key="dash-resets", width="stretch"):
            st.session_state["team_tab"] = "resets"
            st.switch_page(P["team"])
st.write("")

c1, c2, c3, c4 = st.columns(4)
with c1:
    ui.kpi("Open tickets", f"{ts['open']:,}", f"{ts['open_high']} high priority" if ts["total"] else "Nothing triaged yet",
           icon_name="confirmation_number", tone=ui.PRIORITY_COLORS["high"] if ts["open_high"] else None)
with c2:
    ui.kpi("Triaged this week", f"{week_n:,}", f"{ts['total']:,} tickets in total", icon_name="bolt")
with c3:
    ui.kpi("Open tasks", f"{ks['open']:,}", f"{ks['overdue']} overdue" if ks["overdue"] else "None overdue",
           icon_name="task_alt", tone=ui.CRITICAL if ks["overdue"] else None)
with c4:
    if ts["agreement_pct"] is not None:
        ui.kpi("Model priority kept", f"{ts['agreement_pct']:.0f}%",
               f"{ts['corrected']} of {ts['manual_count']} triaged tickets corrected", icon_name="verified")
    else:
        ui.kpi("Model priority kept", "n/a", "Shown once tickets are triaged here", icon_name="verified")

st.write("")

if ts["total"] == 0:
    with st.container(key="card-empty-dash"):
        ui.empty_state(
            "inbox", "No tickets yet",
            "Triage a ticket to see priorities, trends and automated tasks here. You can also import real "
            "historical tickets from the archive to explore the dashboard; they are labelled as archive data.",
        )
        b1, b2, _ = st.columns([1, 1.3, 2])
        if b1.button("Triage a ticket", type="primary", icon=":material/bolt:", width="stretch", key="empty-triage"):
            st.switch_page(P["triage"])
        if b2.button("Import 40 archive tickets", icon=":material/download:", width="stretch", key="empty-import"):
            with st.spinner("Scoring archive tickets with the priority model…"):
                n = import_archive_samples(40, actor=user["login_id"])
            st.toast(f"Imported {n} archive tickets.", icon=":material/check_circle:")
            st.rerun()

left, right = st.columns([2.1, 1], gap="medium")
with left:
    with st.container(key="card-dist"):
        st.markdown("##### Priority of open tickets")
        open_by = {p: 0 for p in ui.PRIORITY_ORDER}
        for t in list_tickets(status=None):
            if t["status"] in ("open", "in_progress") and t["priority"] in open_by:
                open_by[t["priority"]] += 1
        if sum(open_by.values()) == 0:
            st.caption("No open tickets right now.")
        else:
            df = pd.DataFrame({"priority": list(open_by), "n": list(open_by.values())})
            df["label"] = df["priority"].str.capitalize()
            base = alt.Chart(df).encode(
                y=alt.Y("label:N", sort=[p.capitalize() for p in ui.PRIORITY_ORDER], title=None),
                x=alt.X("n:Q", title="Open tickets", axis=alt.Axis(tickMinStep=1, format="d")),
            )
            bars = base.mark_bar(cornerRadiusEnd=4, height=18).encode(
                color=alt.Color("priority:N", scale=alt.Scale(domain=list(ui.PRIORITY_COLORS),
                                                              range=list(ui.PRIORITY_COLORS.values())), legend=None),
                tooltip=[alt.Tooltip("n:Q", title="Open tickets"), alt.Tooltip("label:N", title="Priority")],
            )
            text = base.mark_text(align="left", dx=6, fontSize=12, color=ui.INK).encode(text="n:Q")
            ui.show_chart((bars + text).properties(height=130))

        st.markdown("##### Tickets triaged, last 14 days")
        rows = daily_counts(14, include_archive=False)
        if not rows:
            st.caption("No tickets triaged in the last 14 days. Archive imports are not counted here.")
        else:
            df = pd.DataFrame(rows)
            days = [(date.today() - timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
            full = pd.MultiIndex.from_product([days, ui.PRIORITY_ORDER], names=["day", "priority"])
            df = df.set_index(["day", "priority"]).reindex(full, fill_value=0).reset_index()
            df["Priority"] = df["priority"].str.capitalize()
            chart = alt.Chart(df).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, width={"band": 0.6}).encode(
                x=alt.X("day:O", title=None, axis=alt.Axis(labelAngle=0, labelExpr="slice(datum.value, 5)")),
                y=alt.Y("sum(n):Q", title="Tickets", axis=alt.Axis(tickMinStep=1, format="d")),
                color=alt.Color("Priority:N", sort=[p.capitalize() for p in ui.PRIORITY_ORDER],
                                scale=alt.Scale(domain=[p.capitalize() for p in ui.PRIORITY_ORDER],
                                                range=[ui.PRIORITY_COLORS[p] for p in ui.PRIORITY_ORDER])),
                order=alt.Order("priority:N", sort="descending"),
                tooltip=[alt.Tooltip("day:O", title="Day"), alt.Tooltip("Priority:N"), alt.Tooltip("n:Q", title="Tickets")],
            )
            ui.show_chart(chart.properties(height=200))

with right:
    with st.container(key="card-actions"):
        st.markdown("##### Quick actions")
        with st.container(key="action-1"):
            if st.button("Escalations", icon=":material/assignment_late:", width="stretch", type="primary",
                         key="qa-review"):
                st.switch_page(P["review"])
        with st.container(key="action-2"):
            if st.button("All support tickets", icon=":material/confirmation_number:", width="stretch", key="qa-triage"):
                st.switch_page(P["triage"])
        with st.container(key="action-3"):
            if st.button("Team management", icon=":material/groups:", width="stretch", key="qa-team"):
                st.switch_page(P["team"])
        with st.container(key="action-4"):
            if st.button("Analytics & reports", icon=":material/insights:", width="stretch", key="qa-analytics"):
                st.switch_page(P["analytics"])
        with st.container(key="action-5"):
            label = f"Senior queue ({len(esc_open)} open)" if esc_open else "Senior queue"
            if st.button(label, icon=":material/support_agent:", width="stretch", key="qa-queue"):
                st.switch_page(P["queue"])
        st.caption(f"{len(docs)} document{'s' if len(docs) != 1 else ''} in the Knowledge Hub")

left, right = st.columns([2.1, 1], gap="medium")
with left:
    with st.container(key="card-attention"):
        st.markdown("##### Needs attention")
        urgent = [t for t in list_tickets(priority="high") if t["status"] in ("open", "in_progress")][:5]
        overdue = [t for t in list_tasks() if t["overdue"]][:5]
        if not urgent and not overdue and not esc_open:
            st.caption("Nothing urgent: no open high-priority tickets, overdue tasks or unanswered escalations.")
        for t in urgent:
            a, b = st.columns([5, 1.1], vertical_alignment="center")
            a.markdown(f"{ui.priority_badge('high')} &nbsp;**#{t['id']}** {ui.esc(t['subject'][:90])}"
                       f"<br><span class='pg-muted'>{ui.STATUS_LABELS[t['status']]}, opened {ui.ago(t['created_at'])}</span>",
                       unsafe_allow_html=True)
            if b.button("Open", key=f"att-t-{t['id']}", type="tertiary"):
                st.session_state["focus_ticket"] = t["id"]
                st.switch_page(P["triage"])
        for k in overdue:
            a, b = st.columns([5, 1.1], vertical_alignment="center")
            a.markdown(f"{ui.soft_badge('Overdue task')} &nbsp;{ui.esc(k['title'][:90])}"
                       f"<br><span class='pg-muted'>Was due {ui.ago(k['due_at'])}, {ui.esc(k['assignee'] or 'unassigned')}</span>",
                       unsafe_allow_html=True)
            if b.button("Open", key=f"att-k-{k['id']}", type="tertiary"):
                st.switch_page(P["automation"])
        if esc_open:
            a, b = st.columns([5, 1.1], vertical_alignment="center")
            a.markdown(f"{ui.soft_badge('Senior queue')} &nbsp;{len(esc_open)} question"
                       f"{'s' if len(esc_open) != 1 else ''} waiting for a senior answer", unsafe_allow_html=True)
            if b.button("Open", key="att-q", type="tertiary"):
                st.switch_page(P["queue"])
with right:
    with st.container(key="card-activity"):
        st.markdown("##### Recent activity")
        acts = recent_activity(8)
        if acts:
            ui.activity_feed(acts)
        else:
            st.caption("Actions across PRAGYAAN appear here as your team works.")

with st.container(key="card-self-service"):
    h, btn = st.columns([4, 1], vertical_alignment="center")
    h.markdown("##### Solved by employees with recommended solutions")
    if btn.button("See all", type="tertiary", key="dash-sr-all"):
        st.session_state["rq_tab"] = "self_resolved"
        st.switch_page(P["review"])
    recent_sr = list_tickets(queue="self_resolved", limit=5)
    if not recent_sr:
        st.caption("When an employee closes a ticket with a recommended solution, it's listed here. No action needed.")
    for t in recent_sr:
        src = f"resolved ticket #{t['match_ticket_id']}" if t.get("match_ticket_id") else "the Knowledge Hub"
        sim = f" ({t['match_similarity']:.0%} similar)" if t.get("match_similarity") else ""
        st.markdown(f"{ui.priority_badge(t['priority'])} **#{t['id']}** {ui.esc(ui.clip(t['subject'], 80))}<br>"
                    f"<span class='pg-muted'>{ui.esc(t.get('requester_name') or '')} solved it "
                    f"{ui.ago(t.get('resolved_at'))} with the solution from {src}{sim}</span>",
                    unsafe_allow_html=True)

with st.container(key="card-workload"):
    st.markdown("##### Team workload")
    team = [w for w in workload() if w["is_active"]]
    if not team:
        st.caption("No team members yet. Add Employees and Senior Analysts in Team management.")
    else:
        df = pd.DataFrame([{"Team member": f"{w['name']} ({w['login_id']})",
                            "Role": "Senior Analyst" if w["role"] == "analyst" else "Employee",
                            "Active tickets": int(w["active"] or 0), "High priority": int(w["active_high"] or 0),
                            "Resolved": int(w["resolved"] or 0)} for w in team])
        st.dataframe(df.sort_values(["Active tickets", "Resolved"], ascending=False), hide_index=True, width="stretch")
