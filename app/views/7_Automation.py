"""Workflow Automation: priority rules and the task board."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import ui  # noqa: E402
from copilot.automation import (PRIORITIES, create_rule, create_task, delete_rule, delete_task, list_rules,  # noqa: E402
                                list_tasks, set_task_status, task_stats, update_rule)
from copilot.triage import list_tickets  # noqa: E402

P = st.session_state["_pages"]
user = ui.require_role("analyst")
actor = user["login_id"]

ui.page_header("Workflow Automation",
               "Rules turn each ticket's priority into tasks with an owner and a deadline. "
               "Track them here from to do to done.")

ks = task_stats()
c1, c2, c3, c4 = st.columns(4)
with c1:
    ui.kpi("To do", str(ks["todo"]), icon_name="radio_button_unchecked")
with c2:
    ui.kpi("In progress", str(ks["in_progress"]), icon_name="pending")
with c3:
    ui.kpi("Overdue", str(ks["overdue"]), "Past their deadline" if ks["overdue"] else "Everything on time",
           icon_name="schedule", tone=ui.CRITICAL if ks["overdue"] else None)
with c4:
    sla = f"{ks['sla_met_pct']:.0f}%" if ks["sla_met_pct"] is not None else "n/a"
    ui.kpi("Done within deadline", sla, f"of {ks['sla_measured']} completed tasks" if ks["sla_measured"]
           else "Measured once tasks are completed", icon_name="verified")

open_new = st.session_state.pop("open_new_task", False)
tab_board, tab_rules = st.tabs(["Task board", "Rules"], key="auto_tabs")

# ---------------------------------------------------------------- board
with tab_board:
    with st.expander("New task", icon=":material/add_task:", expanded=open_new):
        tickets = list_tickets(include_archive=False, limit=200)
        with st.form("new_task", border=False, clear_on_submit=True):
            title = st.text_input("Task", placeholder="e.g. Call the customer back about the refund")
            c1, c2, c3, c4 = st.columns([1, 1.2, 1, 2])
            prio = c1.selectbox("Priority", PRIORITIES, index=1, format_func=str.capitalize)
            assignee = c2.text_input("Assignee", placeholder="Name or team")
            hours = c3.number_input("Due in (hours)", min_value=1, max_value=720, value=24)
            link = c4.selectbox("Linked ticket (optional)", [None, *tickets],
                                format_func=lambda t: "None" if t is None else f"#{t['id']} {t['subject'][:50]}")
            desc = st.text_area("Notes", height=70)
            if st.form_submit_button("Create task", type="primary"):
                if not title.strip():
                    st.error("Give the task a title.", icon=":material/edit:")
                else:
                    create_task(title, description=desc or None, ticket_id=link["id"] if link else None,
                                priority=prio, assignee=assignee or None, due_in_hours=hours, created_by=actor)
                    st.toast("Task created.", icon=":material/task_alt:")
                    st.rerun()

    f1, f2, _ = st.columns([1.4, 1, 2])
    who = f1.text_input("Filter by assignee", placeholder="Anyone", key="task_who")
    fp = f2.selectbox("Priority", ["All", *PRIORITIES], format_func=str.capitalize, key="task_prio")
    tasks = list_tasks()
    if who.strip():
        tasks = [t for t in tasks if who.lower() in (t["assignee"] or "").lower()]
    if fp != "All":
        tasks = [t for t in tasks if t["priority"] == fp]

    if not tasks:
        with st.container(key="card-tasks-empty"):
            ui.empty_state("task_alt", "No tasks yet",
                           "Tasks are created automatically when tickets are triaged (see Rules), or add one with "
                           "New task above.")
    else:
        lanes = [("todo", "To do"), ("in_progress", "In progress"), ("done", "Done")]
        cols = st.columns(3, gap="medium")
        for col, (status, label) in zip(cols, lanes):
            items = [t for t in tasks if t["status"] == status]
            shown = items if status != "done" else items[:12]
            with col:
                with st.container(key=f"card-lane-{status}"):
                    st.markdown(f"##### {label} <span class='pg-muted'>({len(items)})</span>", unsafe_allow_html=True)
                    if not items:
                        st.caption("Nothing here.")
                    for t in shown:
                        with st.container(border=True):
                            overdue_html = '<span class="pg-badge pg-prio-high">Overdue</span>' if t["overdue"] else ""
                            st.markdown(f"{ui.priority_badge(t['priority'])} {overdue_html}"
                                        f"<br><b>{ui.esc(t['title'])}</b>", unsafe_allow_html=True)
                            meta = [t["assignee"] or "Unassigned"]
                            if t["ticket_id"]:
                                meta.append(f"ticket #{t['ticket_id']}")
                            if t["due_at"] and status != "done":
                                meta.append(("was due " if t["overdue"] else "due ") + ui.ago(t["due_at"]))
                            if status == "done" and t["completed_at"]:
                                meta.append("done " + ui.ago(t["completed_at"]))
                            if t["source"] in ("rule", "suggested"):
                                meta.append("from a rule")
                            st.caption(", ".join(meta))
                            b1, b2, b3 = st.columns(3)
                            if status != "todo" and b1.button("Back", key=f"bk-{t['id']}", type="tertiary",
                                                              icon=":material/arrow_back:"):
                                set_task_status(t["id"], "todo" if status == "in_progress" else "in_progress", actor)
                                st.rerun()
                            if status != "done" and b2.button("Start" if status == "todo" else "Done",
                                                              key=f"fw-{t['id']}", type="tertiary",
                                                              icon=":material/arrow_forward:" if status == "todo"
                                                              else ":material/check:"):
                                set_task_status(t["id"], "in_progress" if status == "todo" else "done", actor)
                                st.rerun()
                            if t["ticket_id"] and b3.button("Ticket", key=f"tk-{t['id']}", type="tertiary",
                                                            icon=":material/open_in_new:"):
                                st.session_state["focus_ticket"] = t["ticket_id"]
                                st.switch_page(P["triage"])
                    if status == "done" and len(items) > len(shown):
                        st.caption(f"{len(items) - len(shown)} older completed tasks not shown.")

# ---------------------------------------------------------------- rules
with tab_rules:
    st.markdown("When a ticket is saved, every enabled rule for its priority runs. **Auto** rules create the task "
                "immediately; **Suggest** rules show a one-click suggestion on the Smart Triage screen.")
    rules = list_rules()
    df = pd.DataFrame(rules)[["id", "enabled", "name", "priority", "action", "assignee", "sla_hours", "mode"]] \
        if rules else pd.DataFrame(columns=["id", "enabled", "name", "priority", "action", "assignee", "sla_hours", "mode"])
    df["enabled"] = df["enabled"].astype(bool)
    edited = st.data_editor(
        df, hide_index=True, width="stretch", key="rules_editor", disabled=["id"],
        column_config={
            "id": None,
            "enabled": st.column_config.CheckboxColumn("On", width=50),
            "name": st.column_config.TextColumn("Rule", width=190, required=True),
            "priority": st.column_config.SelectboxColumn("Priority", options=list(PRIORITIES), required=True, width=95),
            "action": st.column_config.TextColumn("Task to create", width=300, required=True),
            "assignee": st.column_config.TextColumn("Assign to", width=140),
            "sla_hours": st.column_config.NumberColumn("Due in (h)", min_value=1, max_value=720, step=1, width=90),
            "mode": st.column_config.SelectboxColumn("Mode", options=["auto", "suggest"], required=True, width=95),
        },
    )
    changed = []
    if len(df):
        for (_, a), (_, b) in zip(df.iterrows(), edited.iterrows()):
            diff = {k: b[k] for k in ["enabled", "name", "priority", "action", "assignee", "sla_hours", "mode"]
                    if str(a[k]) != str(b[k])}
            if diff:
                changed.append((int(a["id"]), diff))
    c1, c2, _ = st.columns([1.2, 1.6, 3])
    if c1.button("Save rule changes", type="primary", disabled=not changed, icon=":material/save:", key="rules-save"):
        for rid, diff in changed:
            if "enabled" in diff:
                diff["enabled"] = int(bool(diff["enabled"]))
            if "sla_hours" in diff:
                diff["sla_hours"] = int(diff["sla_hours"])
            update_rule(rid, **diff)
        st.toast(f"Saved {len(changed)} rule{'s' if len(changed) != 1 else ''}.", icon=":material/check_circle:")
        st.rerun()
    if changed:
        c2.caption(f"{len(changed)} unsaved change{'s' if len(changed) != 1 else ''}")

    left, right = st.columns(2, gap="large")
    with left:
        with st.container(key="card-new-rule"):
            st.markdown("##### Add a rule")
            with st.form("new_rule", border=False, clear_on_submit=True):
                name = st.text_input("Rule name", placeholder="e.g. Notify billing team")
                c1, c2 = st.columns(2)
                prio = c1.selectbox("When priority is", PRIORITIES, format_func=str.capitalize)
                mode = c2.selectbox("Mode", ["auto", "suggest"], format_func=lambda m: "Create automatically"
                                    if m == "auto" else "Suggest on triage")
                action = st.text_input("Task to create", placeholder="e.g. Check the payment provider status page")
                c3, c4 = st.columns(2)
                assignee = c3.text_input("Assign to")
                sla = c4.number_input("Due in (hours)", min_value=1, max_value=720, value=24)
                if st.form_submit_button("Add rule", type="primary"):
                    try:
                        create_rule(name, prio, action, int(sla), assignee or None, mode, actor=actor)
                        st.toast("Rule added.", icon=":material/bolt:")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e), icon=":material/error:")
    with right:
        with st.container(key="card-del-rule"):
            st.markdown("##### Remove a rule")
            if rules:
                pick = st.selectbox("Rule", rules, format_func=lambda r: f"{r['name']} ({r['priority']})",
                                    key="del_rule_pick")
                if st.button("Delete rule", icon=":material/delete:", key="rules-delete"):
                    delete_rule(pick["id"])
                    st.toast("Rule deleted.")
                    st.rerun()
                st.caption("Tasks a rule already created are kept. To pause a rule, untick On instead.")
            else:
                st.caption("No rules.")

    with st.expander("Clean up tasks"):
        done = [t for t in list_tasks(status="done")]
        st.caption(f"{len(done)} completed task{'s' if len(done) != 1 else ''}.")
        if done and st.button("Delete completed tasks", icon=":material/delete_sweep:", key="tasks-cleanup"):
            for t in done:
                delete_task(t["id"])
            st.rerun()
