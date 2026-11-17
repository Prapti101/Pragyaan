"""AI Assistant: a normal chat assistant that also knows the company's documents and solved tickets."""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import ui  # noqa: E402
from copilot.assistant import answer_stream, clear_history, history, rate_answer  # noqa: E402
from copilot.knowledge import list_documents  # noqa: E402
from copilot.llm import provider_name  # noqa: E402

P = st.session_state["_pages"]
user = ui.require_role("employee", "analyst")
email = user["login_id"]  # chat history is kept per account
llm = provider_name()

from copilot.triage import archive_available  # noqa: E402

N_ARCHIVE = archive_available()
st.markdown("""<style>
.pg-about { margin: .2rem 0 0; padding: 0; list-style: none; display: grid; gap: .55rem; }
.pg-about li { display: grid; grid-template-columns: auto 1fr; gap: .7rem; align-items: baseline; margin: 0 !important; }
.pg-about b { font-family: var(--display); font-weight: 800; font-size: 1.5rem; line-height: 1; color: var(--lime) !important; }
.pg-about span { font-size: .9rem; line-height: 1.4; color: rgba(244,238,225,.85) !important; }
.pg-about-model { margin: .9rem 0 0 !important; font-size: .82rem; color: rgba(244,238,225,.7) !important; }
</style>""", unsafe_allow_html=True)
ui.masthead(None, "Ask PRAGYAAN",
            "Your company's AI assistant. Ask how something works here, get help with an IT or HR problem, or "
            "have it draft a work email. It knows your company's documents and how past problems were solved.",
            fig=N_ARCHIVE or None, fig_label="solved tickets it has learned from", tone=ui.COBALT, rot=-2)

EXAMPLES = [
    "My VPN keeps disconnecting, what can I try?",
    "Write a polite email asking IT for a new laptop",
    "Explain two-factor authentication in simple words",
]


def _rate(mid: int) -> None:
    v = st.session_state.get(f"fb-{mid}")
    if v is not None:
        rate_answer(mid, email, "up" if v == 1 else "down")


def sources(meta: dict) -> None:
    """Where the background came from, quietly, without scores."""
    docs, tickets = meta.get("doc_sources") or [], meta.get("sources") or []
    if not (docs or tickets) or meta.get("used") == "help":
        return
    with st.expander("Sources", icon=":material/menu_book:"):
        for d in docs:
            st.markdown(f"**{d['title']}** :gray[company document]")
        if tickets:
            st.markdown("Similar solved tickets: " + ", ".join(f"#{t['ticket_id']}" for t in tickets))


def render(msg: dict) -> None:
    meta = msg.get("meta") or {}
    kind = meta.get("kind")
    if msg["role"] == "user":
        with st.chat_message("user", avatar=":material/person:"):
            st.markdown(msg["content"])
        return
    with st.chat_message("assistant", avatar=":material/auto_awesome:"):
        if kind == "senior_answer":
            st.markdown(f":violet-badge[:material/support_agent: Answer from a Senior Analyst] "
                        f":gray[question #{meta.get('escalation_id')}]")
            if meta.get("question"):
                st.caption(f"Your question: {ui.clip(meta['question'], 200)}")
            st.markdown(msg["content"])
        elif kind == "summary":
            st.markdown(f"**{meta.get('title', 'Document')}**, key points:")
            if meta.get("summary"):
                st.markdown(meta["summary"])
            else:
                st.markdown("\n".join(f"- {s}" for s in meta.get("sentences") or [])
                            or "_The document is too short to summarize._")
        elif kind == "escalated":  # older conversations, from before escalation moved to Find a fix
            st.markdown(f"I passed this question to a Senior Analyst (#{meta.get('escalation_id')}). Their answer "
                        "will appear here.")
        else:
            if meta.get("focus_source"):
                st.caption(f"Explaining {meta['focus_source']}")
            st.markdown(msg["content"])
        sources(meta)
        if meta.get("find_fix") and ui.has_page("home") and msg.get("id"):
            if st.button("Check solved tickets in Find a fix", key=f"ff-{msg['id']}", icon=":material/lightbulb:",
                         type="tertiary"):
                st.session_state["home_find_q"] = meta.get("question") or ""
                ui.go("home")
        if kind in ("ai", "documents", "resolved") and msg.get("id"):
            fb = {"up": 1, "down": 0}.get(meta.get("thumbs") or {"resolved": "up", "not_resolved": "down"}.get(meta.get("feedback")))
            st.feedback("thumbs", key=f"fb-{msg['id']}", default=fb, on_change=_rate, args=(msg["id"],))


chat_col, side = st.columns([2.3, 1])

with side:
    n_docs = len(list_documents())
    with st.container(key="card-fit-ink-mode"):
        st.markdown("##### What it knows")
        st.markdown(
            '<ul class="pg-about">'
            f'<li><b>{n_docs:,}</b><span>company document{"s" if n_docs != 1 else ""} from the Knowledge Hub</span></li>'
            + (f'<li><b>{N_ARCHIVE:,}</b><span>solved tickets, used as hints for fixing problems</span></li>'
               if N_ARCHIVE else "")
            + '</ul>'
            + (f"<p class='pg-about-model'>Replies are written by {ui.esc(llm)}.</p>" if llm else
               "<p class='pg-about-model'>No language model connected. Add GROQ_API_KEY to .env to chat; until "
               "then it can only show matching passages.</p>"), unsafe_allow_html=True)
        if ui.has_page("home") and st.button("Find a fix in solved tickets", key="as-find", width="stretch",
                                             icon=":material/lightbulb:"):
            st.session_state["home_mode"] = "find"
            ui.go("home")
    with st.container(key="card-fit-summarize"):
        st.markdown("##### Summarize a document")
        docs = list_documents()
        if not docs:
            st.caption("No documents yet.")
            if st.button("Upload in the Knowledge Hub", icon=":material/upload_file:", width="stretch", key="as-upload"):
                st.switch_page(P["knowledge"])
        else:
            pick = st.selectbox("Document", docs, format_func=lambda d: d["title"], label_visibility="collapsed")
            if st.button("Summarize", icon=":material/summarize:", width="stretch", key="as-summarize"):
                st.session_state["pending_q"] = f"summarize {pick['title']}"
    if history(email):
        with st.container(key="card-fit-examples"):
            st.markdown("##### Try asking")
            for i, ex in enumerate(EXAMPLES):
                if st.button(ex, key=f"ex-{i}", width="stretch", type="tertiary", icon=":material/subdirectory_arrow_right:"):
                    st.session_state["pending_q"] = ex
            if st.button("New chat", icon=":material/add_comment:", width="stretch", key="as-clear"):
                clear_history(email)
                st.rerun()

with chat_col:
    msgs = history(email)
    if not msgs:
        with st.container(key="card-welcome"):
            st.markdown(
                f'<div class="pg-welcome">{ui.sparkle()}'
                f'<h2>{ui.words("How can I help today?")}</h2>'
                '<p>Ask how something works at the company, describe a work problem, or ask for help writing a '
                'work email. Type “summarize” and a document name to get its key points.</p></div>',
                unsafe_allow_html=True)
            cols = st.columns(len(EXAMPLES))
            for i, (col, ex) in enumerate(zip(cols, EXAMPLES)):
                if col.button(ex, key=f"wel-{i}", width="stretch"):
                    st.session_state["pending_q"] = ex
                    st.rerun()
    for m in msgs:
        render(m)

prompt = st.chat_input("Message PRAGYAAN")
pending = st.session_state.pop("pending_q", None)
focus = st.session_state.pop("pending_ctx", None) if pending and not prompt else None
q = prompt or pending
if q:
    with chat_col:
        render({"role": "user", "content": q, "meta": {}})
        with st.chat_message("assistant", avatar=":material/auto_awesome:"):
            try:
                stream = answer_stream(q, user_email=email, focus=focus)
                with st.spinner("Thinking…"):
                    first = next(stream, "")
                st.write_stream(itertools.chain([first], stream))
            except Exception as e:
                st.error(f"The assistant hit an error: {e}", icon=":material/error:")
                st.stop()
    st.rerun()
