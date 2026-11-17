"""Knowledge Hub: upload, organise, search and view documents."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import ui  # noqa: E402
from copilot.knowledge import (SUPPORTED_TYPES, DocumentError, add_document, collections, delete_document,  # noqa: E402
                               document_bytes, document_text, get_document, list_documents, search_documents,
                               summarize, update_document)

P = st.session_state["_pages"]
user = ui.require_role("employee", "analyst")
actor = user["login_id"]
can_edit = user["role"] == "analyst"  # employees read and search; analysts manage documents

def _size(n: int | None) -> str:
    n = int(n or 0)
    return f"{n / 1_048_576:.1f} MB" if n >= 1_048_576 else f"{max(1, n // 1024)} KB"


cols = collections()
col_names = [c["collection"] for c in cols]
docs_all = list_documents()
n_passages = sum(d["chunk_count"] or 0 for d in docs_all)
st.markdown("""<style>
.st-key-card-cobalt-kh-search { padding: 1.5rem 1.6rem 1.3rem !important; border-radius: 20px !important; box-shadow: 8px 8px 0 var(--ink) !important; }
.st-key-card-cobalt-kh-search [data-testid="stTextInputRootElement"] { background: var(--ivory) !important; min-height: 3.4rem; }
.st-key-card-cobalt-kh-search [data-testid="stTextInputRootElement"] :is(input, span) { color: var(--ink) !important; font-size: 1.05rem; }
.st-key-card-cobalt-kh-search [data-testid="stButtonGroup"] button[data-variant] { background: transparent !important; border-color: rgba(244,238,225,.6) !important; }
.st-key-card-cobalt-kh-search [data-testid="stButtonGroup"] button[data-variant] :is(p, span) { color: var(--ivory) !important; }
.st-key-card-cobalt-kh-search [data-testid="stButtonGroup"] button[data-variant]:is([aria-checked="true"], [data-selected="true"], [aria-pressed="true"]) { background: var(--lime) !important; border-color: var(--ink) !important; }
.st-key-card-cobalt-kh-search [data-testid="stButtonGroup"] button[data-variant]:is([aria-checked="true"], [data-selected="true"], [aria-pressed="true"]) :is(p, span) { color: var(--ink) !important; }
.pg-kh-q { font-family: var(--display); font-weight: 800; font-stretch: 86%; font-size: clamp(1.6rem, 3vw, 2.3rem); line-height: 1; letter-spacing: -0.02em; margin: 0 0 .9rem; color: var(--ivory); }
.pg-doc .ic.t-pdf { background: var(--coral); } .pg-doc .ic.t-docx { background: var(--cobalt); color: var(--ivory); } .pg-doc .ic.t-md, .pg-doc .ic.t-txt { background: var(--lime); }
.pg-hit { padding: .85rem 0; border-bottom: 1.5px dashed var(--line); } .pg-hit:last-child { border-bottom: 0; }
.pg-hit p { margin: .35rem 0 0 !important; color: var(--ink-2); font-size: .92rem; line-height: 1.5; }
</style>""", unsafe_allow_html=True)
ui.masthead("Knowledge Hub", "Every answer the company has written down",
            "Policies, guides and runbooks, indexed by meaning so the assistant and search find the right passage, "
            "not just the right keywords." if not can_edit else
            "Upload policies, runbooks and reports. Text is extracted and indexed so the assistant and search find the "
            "right passage by meaning, not just keywords.",
            fig=n_passages, fig_label=f"passages indexed from {len(docs_all)} document{'s' if len(docs_all) != 1 else ''}",
            tone=ui.LIME, rot=-2.5)


if can_edit:
    with st.expander("Upload documents", icon=":material/upload_file:", expanded=not col_names):
        with st.form("upload", border=False, clear_on_submit=True):
            files = st.file_uploader("Files", type=list(SUPPORTED_TYPES), accept_multiple_files=True,
                                     help="PDF, Word (.docx), text, Markdown, CSV, JSON, HTML or log files up to 25 MB each.")
            c1, c2, c3 = st.columns([1.2, 1.2, 1.6])
            existing = c1.selectbox("Collection", ["General", *[c for c in col_names if c != "General"], "New collection…"])
            new_col = c2.text_input("New collection name", placeholder="e.g. HR policies",
                                    disabled=False, help="Used when Collection is set to New collection…")
            tags = c3.text_input("Tags", placeholder="comma separated, e.g. vpn, onboarding")
            submitted = st.form_submit_button("Upload and index", type="primary", icon=":material/cloud_upload:")
        if submitted:
            target = (new_col.strip() if existing == "New collection…" else existing) or "General"
            if not files:
                st.warning("Choose at least one file.", icon=":material/attach_file:")
            else:
                ok, failed = 0, []
                bar = st.progress(0.0, text="Indexing…")
                for i, f in enumerate(files, start=1):
                    bar.progress((i - 1) / len(files), text=f"Extracting and indexing {f.name}…")
                    try:
                        add_document(f.name, f.getvalue(), collection=target,
                                     tags=[t for t in tags.split(",")], actor=actor)
                        ok += 1
                    except DocumentError as e:
                        failed.append(f"{f.name}: {e}")
                    except Exception as e:
                        failed.append(f"{f.name}: indexing failed ({e.__class__.__name__}: {e})")
                bar.empty()
                if ok:
                    st.toast(f"Indexed {ok} document{'s' if ok != 1 else ''} into {target}.", icon=":material/check_circle:")
                for msg in failed:
                    st.error(msg, icon=":material/error:")
                if ok and not failed:
                    st.rerun()


docs_all = list_documents()
if not docs_all:
    with st.container(key="card-kh-empty"):
        if can_edit:
            ui.empty_state("library_books", "Your knowledge hub is empty",
                           "Upload your first documents above. Good starting points: onboarding guides, IT and HR "
                           "policies, runbooks and FAQs.")
        else:
            ui.empty_state("library_books", "No documents yet",
                           "Senior Analysts publish policies, guides and runbooks here. You can still ask the AI "
                           "assistant, which answers from thousands of resolved tickets.")
    st.stop()

options = ["All documents", *col_names]
counts = {"All documents": len(docs_all), **{c["collection"]: c["n"] for c in cols}}
with st.container(key="card-cobalt-kh-search"):
    st.markdown('<div class="pg-kh-q">Search by meaning</div>', unsafe_allow_html=True)
    q = st.text_input("Search documents", placeholder="Describe what you're looking for, e.g. how do I request VPN access",
                      icon=":material/search:", key="kh_q", label_visibility="collapsed")
    if st.session_state.get("kh_collection") not in options:
        st.session_state["kh_collection"] = "All documents"
    chosen = st.segmented_control("Collection", options, format_func=lambda o: f"{o} · {counts.get(o, 0)}",
                                  key="kh_collection", label_visibility="collapsed", required=True) or "All documents"
collection = None if chosen == "All documents" else chosen

main = st.container()
with main:
    if q.strip():
        with st.spinner("Searching by meaning…"):
            hits = search_documents(q, k=8, collection=collection)
        hits = [h for h in hits if h["similarity"] >= 0.2]
        with st.container(key="card-kh-results"):
            st.markdown(f"##### {len(hits)} matching passage{'s' if len(hits) != 1 else ''} for “{ui.esc(ui.clip(q, 60))}”",
                        unsafe_allow_html=True)
            if not hits:
                st.caption("No passage is a close match. Try different words, or check another collection.")
            else:
                from copilot.config import DOC_SIM_THRESHOLD
                st.markdown(ui.ladder([{"label": f"Passage {i + 1}", "sub": ui.clip(h["title"], 22), "sim": h["similarity"]}
                                       for i, h in enumerate(hits)], DOC_SIM_THRESHOLD,
                                      caption="needed for the assistant to answer from it"), unsafe_allow_html=True)
            for i, h in enumerate(hits):
                a, b = st.columns([5, 1], vertical_alignment="top")
                a.markdown(f"<div class='pg-hit'><b>Passage {i + 1} · {ui.esc(h['title'])}</b> {ui.soft_badge(h['collection'])} "
                           f"<span class='pg-muted'>{h['similarity']:.0%} similar</span>"
                           f"<p>{ui.esc(ui.clip(h['text'], 420))}</p></div>", unsafe_allow_html=True)
                if b.button("Open", key=f"hit-{i}-{h['doc_id']}", type="tertiary", icon=":material/arrow_forward:",
                            icon_position="right"):
                    st.session_state["kh_open"] = h["doc_id"]
                    st.rerun()

    docs = list_documents(collection=collection)
    open_id = st.session_state.get("kh_open")
    TYPE_ICON = {"pdf": "picture_as_pdf", "docx": "article", "txt": "notes", "md": "notes", "csv": "table_chart",
                 "json": "data_object", "html": "code", "htm": "code", "log": "terminal"}
    limit = st.session_state.get("kh_limit", 9)
    ui.section("The shelf", f"{len(docs)} document{'s' if len(docs) != 1 else ''}"
               f"{' in ' + collection if collection else ''}")
    for start in range(0, min(len(docs), limit), 3):
        cols = st.columns(3)
        for col, d in zip(cols, docs[start:start + 3]):
            is_open = d["id"] == open_id
            with col, st.container(key=f"card-kdoc-{'open-' if is_open else ''}{d['id']}"):
                ftype = (d["file_type"] or "").lower()
                tags = "".join(ui.soft_badge(t.strip()) + " " for t in (d["tags"] or "").split(",") if t.strip())
                st.markdown(
                    f'<div class="pg-doc"><div class="ic t-{ui.esc(ftype)}">{ui.icon(TYPE_ICON.get(ftype, "description"))}</div>'
                    f'<h4>{ui.esc(ui.clip(d["title"], 60))}</h4>'
                    f'<div class="meta">{ui.esc(d["collection"])} · {ui.esc(ftype.upper() or "FILE")} · '
                    f'{_size(d["size_bytes"])} · {int(d["chunk_count"] or 0)} passages</div>'
                    f'<div class="tags">{tags}</div>'
                    f'<div class="meta">Added {ui.esc(ui.ago(d["uploaded_at"]))}</div></div>',
                    unsafe_allow_html=True)
                if st.button("Reading" if is_open else "Open", key=f"kopen-{d['id']}", width="stretch",
                             type="primary" if is_open else "secondary",
                             icon=":material/menu_book:" if is_open else ":material/open_in_full:"):
                    st.session_state["kh_open"] = d["id"]
                    st.rerun()
    if len(docs) > limit and st.button(f"Show more ({len(docs) - limit} left)", key="kh-more", type="tertiary",
                                       icon=":material/expand_more:"):
        st.session_state["kh_limit"] = limit + 9
        st.rerun()

    doc = get_document(open_id) if open_id else None
    if not doc:
        st.caption("Select a document to view, summarize, edit or delete it." if can_edit
                   else "Select a document to read or summarize it.")
        st.stop()

    with st.container(key="card-doc"):
        h1, h2 = st.columns([3, 1.3], vertical_alignment="top")
        h1.markdown(f"#### {ui.esc(doc['title'])}", unsafe_allow_html=True)
        h1.markdown(f"{ui.soft_badge(doc['collection'])} {ui.soft_badge((doc['file_type'] or '').upper())} "
                    f"<span class='pg-muted'>{ui.esc(doc['filename'])}, {_size(doc['size_bytes'])}, "
                    f"{doc['char_count'] or 0:,} characters, uploaded {ui.esc(ui.ago(doc['uploaded_at']))}</span>",
                    unsafe_allow_html=True)
        try:
            raw = document_bytes(doc["id"])
            h2.download_button("Download original", raw, file_name=doc["filename"], icon=":material/download:",
                               width="stretch")
        except DocumentError as e:
            h2.warning(str(e))
        t_prev, t_sum, *t_rest = st.tabs(["Preview", "Summary", "Details"] if can_edit else ["Preview", "Summary"])
        t_edit = t_rest[0] if t_rest else None
        with t_prev:
            try:
                text = document_text(doc["id"])
                with st.container(height=360, border=True):
                    st.text(text[:20000] + ("\n\n[Preview truncated]" if len(text) > 20000 else ""))
            except DocumentError as e:
                st.error(str(e), icon=":material/error:")
            if st.button("Ask the assistant about this document", icon=":material/forum:", key="kh-ask"):
                st.session_state["pending_q"] = f"summarize {doc['title']}"
                st.switch_page(P["assistant"])
        with t_sum:
            key = f"sum-{doc['id']}"
            if st.button("Summarize", icon=":material/summarize:", key=f"btn-{key}"):
                with st.spinner("Summarizing…"):
                    st.session_state[key] = summarize(doc["id"])
            s = st.session_state.get(key)
            if s:
                if s["method"] == "extractive":
                    st.caption("Extractive summary: the most representative sentences, selected with TF-IDF. "
                               "Connect a language model in .env for written summaries.")
                    st.markdown("\n".join(f"- {x}" for x in s["sentences"]) or "_The document is too short to summarize._")
                else:
                    st.caption(f"Written by {s['method']} from the document text.")
                    st.markdown(s["summary"])
        if t_edit is not None:
            with t_edit:
                with st.form(f"edit-{doc['id']}", border=False):
                    title = st.text_input("Title", value=doc["title"])
                    c1, c2 = st.columns(2)
                    coll = c1.text_input("Collection", value=doc["collection"])
                    tg = c2.text_input("Tags", value=doc["tags"] or "")
                    if st.form_submit_button("Save details", type="primary"):
                        update_document(doc["id"], title=title, collection=coll, tags=tg, actor=actor)
                        st.toast("Details saved.", icon=":material/check_circle:")
                        st.rerun()
                with st.popover("Delete document", icon=":material/delete:"):
                    st.markdown(f"Delete **{doc['title']}**? Its file and search index entries are removed. "
                                "This can't be undone.")
                    if st.button("Delete permanently", type="primary", key=f"del-{doc['id']}"):
                        delete_document(doc["id"], actor=actor)
                        st.session_state.pop("kh_open", None)
                        st.toast("Document deleted.", icon=":material/delete:")
                        st.rerun()
