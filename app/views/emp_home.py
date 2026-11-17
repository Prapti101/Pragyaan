"""Employee home: a command bar (find a fix, raise a ticket), then the employee's tickets."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import ui  # noqa: E402
from copilot.assistant import escalate_question  # noqa: E402
from copilot.config import SIM_THRESHOLD  # noqa: E402
from copilot.triage import TriageUnavailable, find_solutions, list_tickets, my_ticket_counts, self_resolve  # noqa: E402

user = ui.require_role("employee")
c = my_ticket_counts(user["id"])
mine = list_tickets(requester_account_id=user["id"], limit=50)
first = user["name"].split(" ")[0]

if c["suggested"]:
    sub = f"{c['suggested']} of your tickets has a recommended fix waiting. Try it, then close the ticket or escalate it."
elif c["active"]:
    sub = f"{c['active']} ticket{'s are' if c['active'] != 1 else ' is'} with the support team right now."
else:
    sub = "Describe a problem and PRAGYAAN checks thousands of solved tickets and your company's documents first."

st.markdown("""<style>
.st-key-art-cmd { padding: 1.7rem 1.7rem 1.5rem !important; border-radius: 22px !important; box-shadow: 9px 9px 0 var(--cobalt) !important; }
.pg-cmd .hi { font-weight: 650; font-size: .95rem; display: inline-flex; align-items: center; gap: .5rem; color: var(--lime) !important; }
.pg-cmd .hi::before { content: ""; width: 26px; height: 10px; border-radius: 3px; background: var(--lime); }
.pg-cmd h1 { font-family: var(--display) !important; font-weight: 800 !important; font-stretch: 86%; font-size: clamp(2.5rem, 5.4vw, 4.7rem) !important;
  line-height: .92 !important; letter-spacing: -0.025em !important; margin: .7rem 0 .8rem !important; padding: 0 !important; max-width: 13ch; }
.pg-cmd p { font-size: 1.04rem; line-height: 1.5; margin: 0 !important; max-width: 52ch; opacity: .85; }
.st-key-art-cmd [data-testid="stButtonGroup"] button[data-variant] { background: transparent !important; border-color: rgba(244,238,225,.55) !important; }
.st-key-art-cmd [data-testid="stButtonGroup"] button[data-variant] :is(p, span) { color: var(--ivory) !important; }
.st-key-art-cmd [data-testid="stButtonGroup"] button[data-variant]:hover { background: rgba(244,238,225,.12) !important; }
.st-key-art-cmd [data-testid="stButtonGroup"] button[data-variant][aria-checked="true"] { background: var(--lime) !important; border-color: var(--lime) !important; box-shadow: none; }
.st-key-art-cmd [data-testid="stButtonGroup"] button[data-variant][aria-checked="true"] :is(p, span) { color: var(--ink) !important; }
.st-key-art-cmd [data-testid="stTextInputRootElement"] { background: var(--ivory) !important; min-height: 3.3rem; border-color: var(--ivory) !important; }
.st-key-art-cmd [data-testid="stTextInputRootElement"] :is(input, span) { color: var(--ink) !important; font-size: 1.05rem; }
.st-key-art-cmd [data-testid="stFormSubmitButton"] button { min-height: 3.3rem !important; }
.st-key-card-lime-mine .pg-figs { margin-top: 1rem; border-top-color: var(--ink); }
.st-key-card-lime-mine .pg-figs > div { border-right-color: rgba(10,12,27,.25); }
.st-key-card-lime-mine .pg-figs b { font-size: 2.6rem; }
.pg-fix.pg-fill { background: var(--paper); border: var(--edge); border-radius: 14px; box-shadow: var(--hard); padding: 1.15rem 1.15rem 1rem; }
</style>""", unsafe_allow_html=True)

MODES = {"find": ("Find a fix", ":material/lightbulb:", "Describe the problem, e.g. VPN disconnects every few minutes"),
         "raise": ("Raise a ticket", ":material/add_circle:", "Give your ticket a short subject")}
if st.session_state.get("home_mode") not in MODES:
    st.session_state["home_mode"] = "find"
# a problem handed over from the AI Assistant ("Check solved tickets in Find a fix")
handed = st.session_state.pop("home_find_q", None)
if handed:
    st.session_state["home_mode"], st.session_state["home_q"] = "find", handed[:300]
    with st.spinner("Searching solved tickets and documents…"):
        st.session_state["home_solutions"] = (handed, find_solutions(handed))
active = [t for t in mine if t["status"] in ("open", "in_progress", "resolved")]

# ---------------------------------------------------------------- the command slab and the employee's own numbers
top_l, top_r = st.columns([1.7, 1])
with top_l:
    with st.container(key="art-cmd"):
        st.markdown(f'<div class="pg-cmd"><div class="hi">{ui.esc(ui.greeting(user["name"]))}</div>'
                    f'<h1>{ui.words(f"What’s not working, {first}?")}</h1><p>{ui.esc(sub)}</p></div>',
                    unsafe_allow_html=True)
        mode = st.segmented_control("Mode", list(MODES), format_func=lambda m: MODES[m][0], key="home_mode",
                                    required=True, label_visibility="collapsed") or "find"
        with st.form("home-command", border=False, clear_on_submit=False):
            a, b = st.columns([10, 1.7], vertical_alignment="center")
            q = a.text_input("What do you need?", placeholder=MODES[mode][2], label_visibility="collapsed",
                             icon=MODES[mode][1], key="home_q")
            go = b.form_submit_button("Go", type="primary", icon=":material/arrow_upward:", width="stretch")
        if go:
            text = (q or "").strip()
            if not text:
                st.warning("Type something first.", icon=":material/edit:")
            elif mode == "find":
                with st.spinner("Searching solved tickets and documents…"):
                    st.session_state["home_solutions"] = (text, find_solutions(text))
            else:
                st.session_state["sub_subject"] = text[:160]
                ui.go("submit")
with top_r:
    with st.container(key="card-lime-mine"):
        st.markdown("##### Your open tickets")
        st.markdown(f"<div class='pg-big' style='font-size:5.6rem;margin-top:.2rem'>{ui.count(len(active))}</div>"
                    + ui.figures([(ui.count(c["resolved"]), "solved", f"{c['self_resolved']} by you with a recommended fix"),
                                  (ui.count(c["escalated"] + c["in_progress"]), "with the team",
                                   f"{c['escalated']} escalated, {c['in_progress']} in progress")]),
                    unsafe_allow_html=True)
        with st.container(key="actions-mine", horizontal=True, gap="small"):
            if st.button("My tickets", type="primary", key="home-mine", width="stretch", icon=":material/arrow_outward:",
                         icon_position="right"):
                st.session_state["emp_tab"] = "mine"
                ui.go("my_tickets")
            if st.button("New ticket", key="home-new", width="stretch", icon=":material/add:"):
                ui.go("submit")

found = st.session_state.get("home_solutions")
if found:
    with st.container(key="card-recommend"):
        if ui.card_head(f"Fixes for “{ui.esc(ui.clip(found[0], 70))}”", "Clear", key="home-clear", icon_name="close"):
            st.session_state.pop("home_solutions", None)
            st.session_state.pop("home_escalated", None)
            st.rerun()
        n, picked = ui.solution_cards(found[1], "home", pick_label="This solved my problem", explain=True)
        res = found[1]
        best = max([float(res.get("best") or 0)] + [t["similarity"] for t in res.get("tickets") or []])
        sent = st.session_state.get("home_escalated")
        if sent and sent.get("question") == found[0]:
            st.markdown(ui.escalation_panel(sent["explain"]), unsafe_allow_html=True)
            st.success(f"Sent to a Senior Analyst as question #{sent['escalation_id']}. You'll get a notification, "
                       "and their answer will also appear in your AI Assistant chat.", icon=":material/support_agent:")
        else:
            if not n:
                st.info(f"No close match among solved tickets or documents (the closest solved ticket is {best:.0%} "
                        f"similar; {SIM_THRESHOLD:.0%} is needed for a confident fix). A Senior Analyst can answer it.",
                        icon=":material/info:")
            with st.container(key="home-esc-row", horizontal=True, gap="small"):
                with st.popover("Ask a Senior Analyst" if not n else "None of these helped? Ask a Senior Analyst",
                                icon=":material/support_agent:"):
                    note = st.text_area("Anything to add? (optional)", key="home-esc-note", height=90,
                                        placeholder="e.g. I already restarted the router and it still drops")
                    if st.button("Send to a Senior Analyst", key="home-esc-send", type="primary", width="stretch"):
                        neighbors = [{"ticket_id": t["ticket_id"], "similarity": round(t["similarity"], 4),
                                      "snippet": t["snippet"], "answer": (t.get("answer") or "")[:400]}
                                     for t in res.get("tickets") or []]
                        neighbors += [{"ticket_id": f"doc {d['doc_id']}", "similarity": round(d["similarity"], 4),
                                       "snippet": f"{d['title']}: {d['text'][:200]}", "answer": ""}
                                      for d in res.get("documents") or []]
                        try:
                            with st.spinner("Sending to the Senior Queue…"):
                                out = escalate_question(found[0], user["login_id"], best_similarity=best,
                                                        neighbors=neighbors if n else [], note=note)
                        except ValueError as e:
                            st.error(str(e), icon=":material/error:")
                        else:
                            st.session_state["home_escalated"] = {**out, "question": found[0]}
                            st.rerun()
                if st.button("Raise a ticket instead", key="home-esc-ticket", icon=":material/add_circle:"):
                    st.session_state["sub_subject"] = found[0][:160]
                    ui.go("submit")
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

if c["assigned_to_me"]:
    with st.container(key="card-cobalt-assigned"):
        a, b = st.columns([4, 1.3], vertical_alignment="center")
        a.markdown(f"**{c['assigned_to_me']} ticket{'s are' if c['assigned_to_me'] != 1 else ' is'} assigned to you.** "
                   "<span class='pg-muted'>A Senior Analyst asked you to work on "
                   f"{'them' if c['assigned_to_me'] != 1 else 'it'}.</span>", unsafe_allow_html=True)
        if b.button("Open assigned tickets", type="primary", key="home-assigned", width="stretch"):
            st.session_state["emp_tab"] = "assigned"
            ui.go("my_tickets")

# ---------------------------------------------------------------- the latest ticket's journey, and the rest as tickets
if mine:
    ui.section("Where things stand", f"{len(mine)} ticket{'s' if len(mine) != 1 else ''} raised")
    m_l, m_r = st.columns([1.25, 1])
    latest = mine[0]
    with m_l:
        with st.container(key="card-latest"):
            if ui.card_head("Latest update", "View", key="home-latest", icon_name="arrow_forward"):
                st.session_state["focus_ticket"] = latest["id"]
                st.session_state["emp_tab"] = "mine"
                ui.go("my_tickets")
            st.markdown(ui.ticket_stub(latest), unsafe_allow_html=True)
            st.markdown(ui.progress_steps(latest), unsafe_allow_html=True)
            if latest.get("resolution"):
                st.markdown(f'<div class="pg-solution">{ui.esc(ui.clip(latest["resolution"], 260))}</div>',
                            unsafe_allow_html=True)
            elif latest.get("suggested_solution") and latest["stage"] == "suggested":
                st.markdown(f'<div class="pg-solution">{ui.esc(ui.clip(latest["suggested_solution"], 260))}</div>',
                            unsafe_allow_html=True)
    with m_r:
        rest = [t for t in active if t["id"] != latest["id"]][:3]
        st.markdown("##### Also open" if rest else "##### Nothing else open")
        if not rest:
            st.markdown("<p class='pg-muted'>Your other tickets are solved or closed.</p>", unsafe_allow_html=True)
        for t in rest:
            if ui.ticket_tap(t, f"home-{t['id']}", compact=True):
                st.session_state["focus_ticket"] = t["id"]
                st.session_state["emp_tab"] = "mine"
                ui.go("my_tickets")
else:
    with st.container(key="card-first"):
        ui.empty_state("confirmation_number", "No tickets yet",
                       "When something isn't working, describe it above. PRAGYAAN looks for a fix first and raises "
                       "a ticket only if you need one.")

solved = [t for t in mine if t["status"] in ("resolved", "closed") and t.get("resolution")][:3]
if solved:
    ui.section("Fixes that worked for you")
    cols = st.columns(3)
    for col, t in zip(cols, solved):
        by_you = t.get("review_status") == "self_resolved"
        col.markdown(f"<div class='pg-fix pg-fill'><span class='pg-stamp'>{'Solved by you' if by_you else 'Resolved'}</span>"
                     f"<div class='t'>#{t['id']} {ui.esc(ui.clip(t['subject'], 60))}</div>"
                     f"<div class='pg-muted'>{ui.ago(t.get('resolved_at') or t['updated_at'])}</div>"
                     f"<div class='pg-solution'>{ui.esc(ui.clip(t['resolution'], 220))}</div></div>",
                     unsafe_allow_html=True)
