"""Senior engineer escalation queue."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import ui  # noqa: E402
from copilot.db import ensure_db  # noqa: E402
from copilot.escalation import list_open_escalations, resolve_escalation  # noqa: E402

ensure_db()
user = ui.require_role("analyst")
actor = user["login_id"]

ui.page_header("Senior Queue",
               "Questions the assistant couldn't answer, most urgent first. Your answer is added to the knowledge "
               "base, so the same question is answered automatically next time.")

flash = st.session_state.pop("queue_flash", None)
if flash:
    st.success(flash, icon=":material/check_circle:")

escalations = list_open_escalations()

counts = {b: sum(1 for e in escalations if e.get("routing") == b) for b in ("Urgent", "Normal", "Backlog")}
m = st.columns(4)
with m[0]:
    ui.kpi("Open questions", str(len(escalations)), icon_name="support_agent")
with m[1]:
    ui.kpi("Urgent", str(counts["Urgent"]), icon_name="priority_high", tone=ui.CRITICAL if counts["Urgent"] else None)
with m[2]:
    ui.kpi("Normal", str(counts["Normal"]), icon_name="schedule")
with m[3]:
    ui.kpi("Backlog", str(counts["Backlog"]), icon_name="inbox")

if not escalations:
    ui.empty_state("task_alt", "No open questions",
                   "Questions the assistant can't answer from documents or past tickets will appear here.")
    st.stop()

rows = [
    {
        "id": e["id"],
        "routing": e.get("routing"),
        "severity": e.get("severity_label"),
        "score": float(e.get("severity_score") or 0),
        "intent": e.get("intent"),
        "why": "Answer didn't help" if e.get("source") == "not_resolved" else "No close match",
        "question": e.get("question") or "",
        "created": e.get("created_at"),
    }
    for e in escalations
]
st.dataframe(
    rows,
    width="stretch",
    hide_index=True,
    column_config={
        "id": st.column_config.NumberColumn("#", format="%d", width="small"),
        "routing": st.column_config.TextColumn("Priority", width="small"),
        "severity": st.column_config.TextColumn("Severity", width="small"),
        "score": st.column_config.ProgressColumn("Score", min_value=0.0, max_value=1.0, format="%.2f", width="small"),
        "intent": st.column_config.TextColumn("Type", width="small"),
        "why": st.column_config.TextColumn("Why it's here", width="small"),
        "question": st.column_config.TextColumn("Question", width="large"),
        "created": st.column_config.TextColumn("Asked at"),
    },
)

ids = [e["id"] for e in escalations]
selected = st.selectbox(
    "Escalation to answer",
    ids,
    format_func=lambda i: f"#{i}: {next(e['question'] for e in escalations if e['id'] == i)[:90]}",
)
esc = next(e for e in escalations if e["id"] == selected)

with st.container(key="card-escalation"):
    bucket = esc.get("routing") or "Normal"
    color, icon = ui.BUCKET_BADGE.get(bucket, ("gray", ""))
    st.markdown(
        f":{color}-badge[{icon} {bucket}] :gray-badge[Type: {esc.get('intent')}] "
        f":gray[severity {esc.get('severity_label')}, score {float(esc.get('severity_score') or 0):.2f}]"
    )
    st.markdown(f"#### {esc['question']}")
    if esc.get("requester"):
        st.caption(f"Asked by {esc['requester']} · {ui.ago(esc.get('created_at'))}. Your answer is sent back to them "
                   "in the assistant chat.")
    if esc.get("source") == "not_resolved":
        st.markdown(ui.label("The assistant answered, but the employee says it didn't solve the problem") +
                    f'<div class="pg-solution">{ui.esc(ui.clip(esc.get("attempted_answer") or "", 900))}</div>',
                    unsafe_allow_html=True)
        if esc.get("employee_note"):
            st.markdown(ui.label("What's still wrong, in their words") +
                        f"<div style='color:var(--ink)'>{ui.esc(esc['employee_note'])}</div>", unsafe_allow_html=True)
    terms = esc.get("reason_terms") or []
    if terms:
        st.markdown("**Why it scored this way:** " + " ".join(f":gray-badge[{t}]" for t in terms))

    left, right = st.columns([1, 1], gap="large")
    with left:
        st.markdown("**Closest past tickets**")
        for n in esc.get("neighbors") or []:
            ans = str(n.get("answer", ""))[:200]
            st.markdown(
                f"**Ticket {n.get('ticket_id')}** :gray[{float(n.get('similarity') or 0):.0%} match]  \n"
                f"{ui.clip(n.get('snippet', ''), 160)}" + (f"  \n:gray[Answer: {ans}]" if ans else "")
            )
    with right:
        resolution = st.text_area(
            "Your answer (added to the knowledge base)",
            height=180,
            key=f"resolution-{esc['id']}",
            placeholder="Steps, links or the person to contact",
        )
        if st.button("Resolve and add to knowledge base", type="primary", key="queue-resolve"):
            if not resolution.strip():
                st.error("Write an answer before resolving.")
            else:
                result = resolve_escalation(esc["id"], resolution.strip(), resolved_by=actor)
                st.session_state["queue_flash"] = (
                    f"Resolved #{result['escalation_id']} and added it to the knowledge base as ticket "
                    f"{result['kb_ticket_id']}." + (" The answer was sent to the person who asked."
                                                    if esc.get("requester") else
                                                    " Ask the same question in the AI Assistant to see it answered.")
                )
                st.rerun()
