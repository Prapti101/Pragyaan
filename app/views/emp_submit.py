"""Employee: submit a support ticket (priority prediction + similarity routing)."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import ui  # noqa: E402
from copilot.config import SIM_THRESHOLD  # noqa: E402
from copilot.triage import (TriageUnavailable, accept_suggestion, decline_suggestion, find_solutions,  # noqa: E402
                            model_status, self_resolve, submit_ticket)

user = ui.require_role("employee")
ui.page_header("Submit a support ticket",
               "Describe the problem. PRAGYAAN predicts its priority and looks for a matching solution among resolved "
               "tickets. If one fits, you can close the ticket yourself; if not, it goes to a Senior Analyst.")

ms = model_status()
if not ms["ok"]:
    st.error(f"The priority model isn't available, so tickets can't be triaged right now. {ms['message']}",
             icon=":material/error:")


def track(tid: int) -> None:
    st.session_state["focus_ticket"] = tid
    st.session_state["emp_tab"] = "mine"
    for k in ("emp_submitted", "emp_self_resolved"):
        st.session_state.pop(k, None)
    ui.go("my_tickets")


# ---------------------------------------------------------------- solved from a recommendation, no ticket needed
solved = st.session_state.get("emp_self_resolved")
if solved:
    with st.container(key="card-self-resolved"):
        st.markdown("#### Glad that solved it")
        st.success(f"Recorded as ticket #{solved['id']} and closed as solved with the recommended solution. It appears "
                   "on the Senior Analysts' dashboard as completed; nothing was escalated.",
                   icon=":material/check_circle:")
        st.markdown(f'<div class="pg-solution">{ui.esc(ui.clip(solved["resolution"], 900))}</div>',
                    unsafe_allow_html=True)
        st.write("")
        c1, c2, _ = st.columns([1, 1, 2])
        if c1.button("View in My tickets", type="primary", icon=":material/visibility:", key="sr-track",
                     width="stretch"):
            track(solved["id"])
        if c2.button("Raise another", icon=":material/add:", key="sr-another", width="stretch"):
            st.session_state.pop("emp_self_resolved", None)
            st.rerun()
    st.stop()

# ---------------------------------------------------------------- just submitted
done = st.session_state.get("emp_submitted")
if done:
    t, pred = done["ticket"], done["prediction"]
    with st.container(key="card-submitted"):
        st.markdown(f"#### Ticket #{t['id']} submitted")
        st.markdown(f"{ui.stage_badge(t['stage'])} {ui.priority_badge(t['priority'])} &nbsp;"
                    f"<span class='pg-muted'>{ui.esc(t['subject'])}</span>", unsafe_allow_html=True)
        st.markdown(ui.progress_steps(t), unsafe_allow_html=True)
        a, b = st.columns([1, 1.3], gap="large")
        with a:
            st.markdown("**Predicted priority**")
            st.markdown(ui.prob_meter(pred["probabilities"], pred["priority"]), unsafe_allow_html=True)
            st.caption(f"{pred['model_name']}, {pred['confidence']:.0%} confident. A Senior Analyst can adjust it.")
        with b:
            if t["stage"] == "suggested":
                st.markdown(f"**Recommended solution** <span class='pg-muted'>from resolved ticket "
                            f"#{t['match_ticket_id']} · {t['match_similarity']:.0%} similar</span>",
                            unsafe_allow_html=True)
                st.markdown(f'<div class="pg-solution">{ui.esc(t["suggested_solution"] or "")}</div>',
                            unsafe_allow_html=True)
                st.caption("Try it. If it fixes the problem, close the ticket; if not, send it to a Senior Analyst.")
                c1, c2 = st.columns(2)
                if c1.button("This solved my issue", type="primary", icon=":material/check_circle:", key="sub-accept",
                             width="stretch"):
                    done["ticket"] = accept_suggestion(t["id"], user)
                    st.rerun()
                with c2.popover("Not solved, escalate", icon=":material/support_agent:", width="stretch"):
                    why = st.text_area("What didn't work? (optional)", key="sub-why", height=90)
                    if st.button("Escalate to a Senior Analyst", type="primary", key="sub-decline", width="stretch"):
                        done["ticket"] = decline_suggestion(t["id"], user, why)
                        st.rerun()
            elif t["stage"] == "closed":
                st.success("Closed as solved with the recommended solution. The Senior Analysts see it on their "
                           "dashboard as completed.", icon=":material/check_circle:")
            elif t.get("review_status") == "declined":
                st.info("Escalated to the Senior Analysts with your note. You'll be notified when someone picks it up.",
                        icon=":material/support_agent:")
            else:
                st.markdown("**Routing**")
                st.info(f"No resolved ticket was a close enough match (at least {SIM_THRESHOLD:.0%} similar), so it "
                        "went straight to the Senior Analysts' escalation queue.", icon=":material/support_agent:")
        c1, c2, _ = st.columns([1, 1, 2])
        if c1.button("Track in My tickets", icon=":material/visibility:", key="sub-track", width="stretch"):
            track(t["id"])
        if c2.button("Submit another", icon=":material/add:", key="sub-another", width="stretch"):
            st.session_state.pop("emp_submitted", None)
            st.rerun()
    st.stop()

# ---------------------------------------------------------------- form
left, right = st.columns([1.25, 1], gap="large")
with left:
    with st.container(key="card-submit-form"):
        with st.form("submit-ticket", border=False):
            subject = st.text_input("Subject", key="sub_subject", max_chars=160,
                                    placeholder="e.g. Can't access the payroll portal since this morning")
            body = st.text_area("Description", key="sub_body", height=190, max_chars=5000,
                                placeholder="What happened, since when, who is affected, and any error message.")
            b1, b2 = st.columns(2)
            check = b1.form_submit_button("Check existing solutions", icon=":material/lightbulb:", width="stretch")
            submit = b2.form_submit_button("Submit ticket", type="primary", icon=":material/send:", width="stretch",
                                           disabled=not ms["ok"])
        if check:
            text = f"{subject}. {body}".strip(". ")
            if len(text) < 6:
                st.warning("Write a subject or description first.", icon=":material/edit:")
            else:
                with st.spinner("Searching resolved tickets and documents…"):
                    st.session_state["sub_solutions"] = find_solutions(text)
                    st.session_state["sub_query"] = (subject, body)
        if submit:
            try:
                with st.spinner("Predicting priority and searching resolved tickets…"):
                    out = submit_ticket(subject, body, user)
            except (ValueError, TriageUnavailable) as e:
                st.error(str(e), icon=":material/error:")
            else:
                st.session_state["emp_submitted"] = out
                for k in ("sub_subject", "sub_body", "sub_solutions", "sub_query"):
                    st.session_state.pop(k, None)
                st.rerun()
with right:
    with st.container(key="card-submit-help"):
        st.markdown("##### Existing solution recommendations")
        sol = st.session_state.get("sub_solutions")
        if sol is None:
            st.caption("Click **Check existing solutions** to see how similar problems were solved before. If one "
                       "fixes it, mark it as solved: no ticket goes to the Senior Analysts.")
            st.markdown("##### What happens when you submit")
            st.markdown(
                "1. The priority model scores your ticket as **low**, **medium** or **high**.\n"
                "2. The similarity engine compares it with thousands of resolved tickets.\n"
                f"3. A close match (at least {SIM_THRESHOLD:.0%} similar): you get its solution right away. Close the "
                "ticket if it works, or escalate it with one click.\n"
                "4. No close match: it goes straight to the Senior Analysts.\n"
                "5. Follow every step in **My tickets**.")
        else:
            n, picked = ui.solution_cards(sol, "sub", pick_label="This solved my problem")
            if not n:
                st.info("Nothing close enough among resolved tickets or documents. Submit the ticket and the support "
                        "team will handle it.", icon=":material/info:")
            if picked:
                q_subject, q_body = st.session_state.get("sub_query") or ("", "")
                try:
                    with st.spinner("Recording the solved issue…"):
                        st.session_state["emp_self_resolved"] = self_resolve(q_subject, q_body, picked, user)
                except (ValueError, TriageUnavailable) as e:
                    st.error(str(e), icon=":material/error:")
                else:
                    for k in ("sub_subject", "sub_body", "sub_solutions", "sub_query"):
                        st.session_state.pop(k, None)
                    st.rerun()
