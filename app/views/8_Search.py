"""Global search results across tickets, documents, tasks and the ticket archive."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import ui  # noqa: E402
from copilot.globalsearch import search_all  # noqa: E402

P = st.session_state["_pages"]
user = ui.require_role("employee", "analyst")
is_analyst = user["role"] == "analyst"
q = st.session_state.get("search_q", "")

scope = "tickets, documents, tasks and the archive" if is_analyst else "your tickets, documents and past solutions"
ui.page_header("Search", f"Results for “{q}”" if q else f"Search across {scope}.")
q2 = st.text_input("Search again", value=q, icon=":material/search:", label_visibility="collapsed",
                   placeholder=f"Search {scope}…", key="search_page_q")
if q2.strip() and q2.strip() != q:
    st.session_state["search_q"] = q = q2.strip()
    st.rerun()
if not q:
    ui.empty_state("search", "Type something to search", "Use the search box at the top of any page.")
    st.stop()

with st.spinner("Searching…"):
    r = search_all(q, actor=user)
for err in r["errors"]:
    st.warning(err, icon=":material/warning:")

total = len(r["tickets"]) + len(r["documents"]) + len(r["doc_passages"]) + len(r["tasks"]) + len(r["archive"])
if total == 0:
    ui.empty_state("search_off", "No results", "Try fewer or different words.")
    st.stop()

left, right = st.columns(2, gap="large")
with left:
    with st.container(key="card-s-tickets"):
        st.markdown(f"##### {'Tickets' if is_analyst else 'Your tickets'} ({len(r['tickets'])})")
        if not r["tickets"]:
            st.caption("No ticket matches. Tickets are searched by words and by meaning." if is_analyst else
                       "None of your tickets (raised by you or assigned to you) match.")
        for t in r["tickets"]:
            why = []
            if t.get("matched_words"):
                why.append("contains " + ", ".join(t["matched_words"][:4]))
            if t.get("similarity") is not None:
                why.append(f"similar meaning {t['similarity']:.2f}")
            a, b = st.columns([5, 1], vertical_alignment="center")
            a.markdown(f"{ui.priority_badge(t['priority'])} **#{t['id']}** {ui.esc(ui.clip(t['subject'], 90))}<br>"
                       f"<span class='pg-muted'>{ui.STATUS_LABELS.get(t['status'], t['status'])}, "
                       f"{ui.esc(ui.ago(t['created_at']))}{', ' + ui.esc('; '.join(why)) if why else ''}</span>",
                       unsafe_allow_html=True)
            if b.button("Open", key=f"s-t-{t['id']}", type="tertiary"):
                st.session_state["focus_ticket"] = t["id"]
                ui.go("triage" if is_analyst else "my_tickets")
    if is_analyst:
        with st.container(key="card-s-tasks"):
            st.markdown(f"##### Tasks ({len(r['tasks'])})")
            if not r["tasks"]:
                st.caption("No task matches these words.")
            for t in r["tasks"]:
                st.markdown(f"{ui.priority_badge(t['priority'])} {ui.esc(t['title'])} "
                            f"<span class='pg-muted'>{ui.STATUS_LABELS.get(t['status'], t['status'])}</span>",
                            unsafe_allow_html=True)
            if r["tasks"] and st.button("Open task board", type="tertiary", icon=":material/account_tree:", key="s-board"):
                st.switch_page(P["automation"])
with right:
    with st.container(key="card-s-docs"):
        st.markdown(f"##### Documents ({len(r['documents']) + len(r['doc_passages'])})")
        if not r["documents"] and not r["doc_passages"]:
            st.caption("No document matches.")
        for d in r["documents"]:
            a, b = st.columns([5, 1], vertical_alignment="center")
            a.markdown(f"**{ui.esc(d['title'])}** {ui.soft_badge(d['collection'])}", unsafe_allow_html=True)
            if b.button("Open", key=f"s-d-{d['id']}", type="tertiary"):
                st.session_state["kh_open"] = d["id"]
                st.switch_page(P["knowledge"])
        for i, h in enumerate(r["doc_passages"]):
            a, b = st.columns([5, 1], vertical_alignment="top")
            a.markdown(f"**{ui.esc(h['title'])}** <span class='pg-muted'>passage, similarity {h['similarity']:.2f}</span>",
                       unsafe_allow_html=True)
            a.caption(ui.clip(h["text"], 240))
            if b.button("Open", key=f"s-p-{i}", type="tertiary"):
                st.session_state["kh_open"] = h["doc_id"]
                st.switch_page(P["knowledge"])
    with st.container(key="card-s-archive"):
        st.markdown("##### Closest tickets in the archive")
        st.caption("Semantic matches from the 9.5k resolved historical tickets.")
        for h in r["archive"]:
            st.markdown(f"{ui.priority_badge(h['priority']) if h.get('priority') else ''} **#{h['ticket_id']}** "
                        f"<span class='pg-muted'>similarity {h['similarity']:.2f}</span><br>{ui.esc(ui.clip(h['snippet'], 180))}",
                        unsafe_allow_html=True)
        if st.button("Ask the assistant about this", icon=":material/forum:", type="tertiary", key="s-ask"):
            st.session_state["pending_q"] = q
            st.switch_page(P["assistant"])
