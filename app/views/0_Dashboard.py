"""Senior Analyst: enterprise operations overview (queues, priorities, self-service, model, team, activity)."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import ui  # noqa: E402
from copilot.activity import recent_activity  # noqa: E402
from copilot.auth import list_accounts, list_reset_requests  # noqa: E402
from copilot.automation import list_tasks, task_stats  # noqa: E402
from copilot.db import fetchone  # noqa: E402
from copilot.escalation import list_open_escalations  # noqa: E402
from copilot.triage import (daily_counts, import_archive_samples, list_tickets, model_name, queue_counts,  # noqa: E402
                            self_service_stats, ticket_stats, workload)

P = st.session_state["_pages"]
user = ui.require_role("analyst")

ts = ticket_stats(include_archive=True)
ks = task_stats()
qc = queue_counts()
ss = self_service_stats()
esc_open = list_open_escalations()
resets = list_reset_requests(user)
team = list_accounts(active_only=True)
week = fetchone("SELECT COUNT(*) AS n FROM tickets WHERE source = 'manual' AND created_at >= datetime('now', '-7 days')")
week_n = int(week["n"]) if week else 0
open_by = {p: 0 for p in ui.PRIORITY_ORDER}
active_rows = list_tickets(queue="active")
for t in active_rows:
    if t["priority"] in open_by:
        open_by[t["priority"]] += 1

# The headline states what needs the analyst right now, from live counts.
needs = qc["escalated"] + len(esc_open) + len(resets)
if needs:
    parts = []
    if qc["escalated"]:
        parts.append(f"{qc['escalated']} escalated ticket{'s' if qc['escalated'] != 1 else ''}")
    if esc_open:
        parts.append(f"{len(esc_open)} unanswered question{'s' if len(esc_open) != 1 else ''}")
    if resets:
        parts.append(f"{len(resets)} password reset{'s' if len(resets) != 1 else ''}")
    title = f"{needs} thing{'s' if needs != 1 else ''} need{'s' if needs == 1 else ''} you today"
    sub = "Waiting: " + ", ".join(parts) + "."
else:
    title = "The support floor is calm"
    sub = "No escalations, unanswered questions or reset requests are waiting."

if "@" in user["login_id"]:
    st.info("Your sign-in ID is still your old e-mail address. Give yourself a Senior Analyst ID (e.g. SA-001) in "
            "Team management; you'll sign in with it from then on.", icon=":material/badge:")

# ---------------------------------------------------------------- the headline, the team, the next step
h_left, h_right = st.columns([1.7, 1], vertical_alignment="bottom")
with h_left:
    ui.masthead(ui.greeting(user["name"]), title, sub)
with h_right:
    st.markdown(f"<div style='display:flex;align-items:center;justify-content:flex-end;gap:.8rem'>"
                f"<span class='pg-muted'>Your team · {len(team)} active</span>{ui.avatars([a['name'] for a in team])}</div>",
                unsafe_allow_html=True)
    with st.container(key="hero-actions", horizontal=True, horizontal_alignment="right", gap="small"):
        if qc["escalated"] and st.button("Work escalations", type="primary", icon=":material/assignment_late:",
                                         key="hero-esc"):
            st.session_state["rq_tab"] = "escalated"
            st.switch_page(P["review"])
        if st.button("Manage team", icon=":material/group_add:", key="hero-team"):
            st.session_state["team_tab"] = "resets" if resets else "people"
            st.switch_page(P["team"])

if ts["total"] == 0:
    with st.container(key="card-empty-dash"):
        ui.empty_state(
            "inbox", "No tickets yet",
            "Triage a ticket to see priorities, trends and automated tasks here. You can also import real "
            "historical tickets from the archive to explore the dashboard; they are labelled as archive data.",
        )
        with st.container(key="actions-empty", horizontal=True, horizontal_alignment="center", gap="small"):
            if st.button("Triage a ticket", type="primary", icon=":material/bolt:", key="empty-triage"):
                st.switch_page(P["triage"])
            if st.button("Import 40 archive tickets", icon=":material/download:", key="empty-import"):
                with st.spinner("Scoring archive tickets with the priority model…"):
                    n = import_archive_samples(40, actor=user["login_id"])
                st.toast(f"Imported {n} archive tickets.", icon=":material/check_circle:")
                st.rerun()

# ---------------------------------------------------------------- the floor: open tickets by priority, the most urgent as tickets
RANK = {p: i for i, p in enumerate(ui.PRIORITY_ORDER)}
urgent = sorted(active_rows, key=lambda t: (RANK.get(t["priority"], 9), -int(t["id"])))[:4]
with st.container(key="card-ink-floor"):
    f_l, f_r = st.columns([1, 1.25], gap="large")
    with f_l:
        n_open = sum(open_by.values())
        st.markdown(f'<div class="pg-sec"><h3>Open by priority</h3><span>{n_open} open</span></div>', unsafe_allow_html=True)
        st.markdown(ui.ribbon(open_by), unsafe_allow_html=True)
        st.markdown(f"<p class='pg-muted' style='margin:.2rem 0 0'>Coloured by the priority each ticket has now: the model's "
                    f"prediction, or a Senior Analyst's correction. {ts['corrected']} corrected so far.</p>",
                    unsafe_allow_html=True)
        if st.button("All tickets", key="floor-all", type="tertiary", icon=":material/arrow_forward:", icon_position="right"):
            st.switch_page(P["triage"])
    with f_r:
        if not urgent:
            st.markdown("##### Nothing open")
            st.markdown("<p class='pg-muted'>Every ticket is solved or closed.</p>", unsafe_allow_html=True)
        else:
            st.markdown("##### Most urgent first")
            grid = st.columns(2) if len(urgent) > 1 else [st.container()]
            for k, t in enumerate(urgent):
                with grid[k % len(grid)]:
                    if ui.ticket_tap(t, f"floor-{t['id']}", compact=True, show_requester=True):
                        st.session_state["focus_ticket"] = t["id"]
                        st.switch_page(P["triage"])

# ---------------------------------------------------------------- escalations, inflow, how much the system handles on its own
c1, c2, c3 = st.columns([1, 1.55, 1.1])
with c1:
    with st.container(key="card-lime-esc"):
        st.markdown("##### Escalations")
        st.markdown(f"<div class='pg-big' style='font-size:5.4rem;margin-top:.3rem'>{ui.count(qc['escalated'])}</div>"
                    f"<div style='margin-top:.5rem;font-weight:600'>need an owner</div>"
                    f"<div class='pg-muted' style='margin-top:.2rem'>{qc['assigned']} assigned · {qc['waiting']} waiting on "
                    f"the employee</div>", unsafe_allow_html=True)
        if st.button("Open escalations", key="ctl-esc", type="primary", icon=":material/arrow_outward:",
                     icon_position="right", width="stretch"):
            st.session_state["rq_tab"] = "escalated"
            st.switch_page(P["review"])
with c2:
    with st.container(key="card-trend"):
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
            chart = alt.Chart(df).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, width={"band": 0.6},
                                           stroke=ui.SURFACE, strokeWidth=1.5).encode(
                x=alt.X("day:O", title="Day of the month", axis=alt.Axis(labelAngle=0, labelExpr="slice(datum.value, 8)")),
                y=alt.Y("sum(n):Q", title="Tickets", axis=alt.Axis(tickMinStep=1, format="d")),
                color=alt.Color("Priority:N", sort=[p.capitalize() for p in ui.PRIORITY_ORDER],
                                scale=alt.Scale(domain=[p.capitalize() for p in ui.PRIORITY_ORDER],
                                                range=[ui.PRIORITY_COLORS[p] for p in ui.PRIORITY_ORDER]),
                                legend=alt.Legend(orient="top", title=None)),
                order=alt.Order("priority:N", sort="descending"),
                tooltip=[alt.Tooltip("day:O", title="Day"), alt.Tooltip("Priority:N"), alt.Tooltip("n:Q", title="Tickets")],
            )
            ui.show_chart(chart.properties(height=190))
with c3:
    with st.container(key="card-health"):
        st.markdown("##### Handled without a person")
        rate, kept = ss["rate_pct"], ts["agreement_pct"]
        st.markdown(
            "<div style='display:grid;grid-template-columns:1fr 1fr;gap:.4rem;align-items:start'>"
            + ui.ring_gauge(rate, f"{rate:.0f}%" if rate is not None else "–",
                            f"self-service · {ss['total']} solved by employees, {ss['recent']} this week", size=124)
            + ui.ring_gauge(kept, f"{kept:.0f}%" if kept is not None else "–",
                            f"priorities kept · {ts['corrected']} of {ts['manual_count']} corrected", size=124, tone=ui.CORAL)
            + "</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------- what just happened, what's coming in, what's late
left, right = st.columns([1.15, 1])
with left:
    with st.container(key="card-ink-latest"):
        st.markdown("##### Latest on the floor")
        acts = [a for a in recent_activity(20) if a["kind"] != "login"][:6]
        if acts:
            ui.activity_feed([{**a, "message": ui.clip(a["message"], 110)} for a in acts])
        else:
            st.caption("Actions across PRAGYAAN appear here as your team works.")
        if esc_open and st.button(f"Senior queue · {len(esc_open)} open", key="ctl-queue", type="tertiary",
                                  icon=":material/support_agent:"):
            st.switch_page(P["queue"])
with right:
    with st.container(key="card-inflow"):
        st.markdown("##### Tickets raised, last 5 days")
        st.markdown(ui.day_strip(daily_counts(5, include_archive=False), 5), unsafe_allow_html=True)
        st.caption(f"{week_n} raised in the last 7 days · {ts['total']:,} tickets in total · "
                   f"{ts['open_high']} high priority open")
    with st.container(key="card-tasks"):
        overdue = [t for t in list_tasks() if t["overdue"]][:3]
        st.markdown(f"##### Overdue tasks <span class='pg-muted' style='font-size:.85rem;font-weight:600'>"
                    f"{ks['overdue']} of {ks['open']} open</span>", unsafe_allow_html=True)
        if not overdue:
            st.caption("No task is past its deadline.")
        for k in overdue:
            with st.container(key=f"line-att-k-{k['id']}", horizontal=True, vertical_alignment="center", wrap=False):
                st.markdown(f"<div class='pg-item' style='padding:0;border:0'><div>"
                            f"<div class='t' style='margin:0'>{ui.esc(ui.clip(k['title'], 80))}</div>"
                            f"<div class='s'>Was due {ui.ago(k['due_at'])}</div></div></div>", unsafe_allow_html=True,
                            width="stretch")
                if st.button("Open", key=f"att-k-{k['id']}", type="tertiary", icon=":material/arrow_forward:",
                             icon_position="right"):
                    st.switch_page(P["automation"])

# ---------------------------------------------------------------- row 5: self-service + workload
left, right = st.columns([1.25, 1])
with left:
    with st.container(key="card-self-service"):
        if ui.card_head("Solved by employees with recommended solutions", "See all", key="dash-sr-all",
                        icon_name="arrow_forward"):
            st.session_state["rq_tab"] = "self_resolved"
            st.switch_page(P["review"])
        recent_sr = list_tickets(queue="self_resolved", limit=5)
        if not recent_sr:
            st.caption("When an employee closes a ticket with a recommended solution, it's listed here. No action needed.")
        items = []
        for t in recent_sr:
            src = f"resolved ticket #{t['match_ticket_id']}" if t.get("match_ticket_id") else "the Knowledge Hub"
            sim = f" ({t['match_similarity']:.0%} similar)" if t.get("match_similarity") else ""
            items.append(f"<div class='pg-item'><div><div>{ui.priority_badge(t['priority'])}</div>"
                         f"<div class='t'><b>#{t['id']}</b> {ui.esc(ui.clip(t['subject'], 80))}</div>"
                         f"<div class='s'>{ui.esc(t.get('requester_name') or '')} solved it {ui.ago(t.get('resolved_at'))} "
                         f"with the solution from {src}{sim}</div></div></div>")
        if items:
            st.markdown("<div>" + "".join(items) + "</div>", unsafe_allow_html=True)
with right:
    with st.container(key="card-workload"):
        st.markdown("##### Team workload")
        load = [w for w in workload() if w["is_active"]]
        if not load:
            st.caption("No team members yet. Add Employees and Senior Analysts in Team management.")
        else:
            load.sort(key=lambda w: (-int(w["active"] or 0), -int(w["resolved"] or 0)))
            st.markdown(ui.hbars([{
                "name": w["name"], "sub": "Senior Analyst" if w["role"] == "analyst" else "Employee",
                "parts": [(int(w["active_high"] or 0), ui.CORAL, "High priority, active"),
                          (int(w["active"] or 0) - int(w["active_high"] or 0), ui.COBALT, "Other active")],
                "value_html": f"<b>{int(w['active'] or 0)}</b> active · {int(w['resolved'] or 0)} resolved",
            } for w in load[:8]]), unsafe_allow_html=True)
            st.markdown(f"<div class='pg-meter-legend'><span><i style='background:{ui.CORAL}'></i>High priority</span>"
                        f"<span><i style='background:{ui.COBALT}'></i>Other active tickets</span></div>",
                        unsafe_allow_html=True)
