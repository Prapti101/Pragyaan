"""Knowledge Hub: store documents, extract text, index chunks for semantic search."""

from __future__ import annotations

import io
import json
import re
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from .activity import log_activity
from .config import CHROMA_DIR, DOC_COLLECTION_NAME, DOCS_DIR
from .db import execute, fetchall, fetchone

SUPPORTED_TYPES = ("txt", "md", "csv", "json", "log", "html", "htm", "pdf", "docx")
MAX_BYTES = 25 * 1024 * 1024
CHUNK_CHARS = 900
CHUNK_OVERLAP = 150


class DocumentError(ValueError):
    """Message is safe to show to the user."""


# ---------------------------------------------------------------- text extraction

def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:  # integration point
        raise DocumentError("PDF support needs the pypdf package: pip install pypdf") from e
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as e:
        raise DocumentError(f"Could not read this PDF ({e.__class__.__name__}).") from e


def _docx_text(data: bytes) -> str:
    """DOCX without extra dependencies: paragraphs from word/document.xml."""
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            root = ElementTree.fromstring(z.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as e:
        raise DocumentError("This .docx file could not be opened.") from e
    paras = []
    for p in root.iter(f"{ns}p"):
        text = "".join(t.text or "" for t in p.iter(f"{ns}t"))
        if text.strip():
            paras.append(text)
    return "\n\n".join(paras)


def _html_text(data: bytes) -> str:
    from html.parser import HTMLParser

    class _P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts, self._skip = [], 0

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style"):
                self._skip += 1
            elif tag in ("p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr"):
                self.parts.append("\n")

        def handle_endtag(self, tag):
            if tag in ("script", "style") and self._skip:
                self._skip -= 1

        def handle_data(self, d):
            if not self._skip:
                self.parts.append(d)

    p = _P()
    p.feed(_decode(data))
    return "".join(p.parts)


def extract_text(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in SUPPORTED_TYPES:
        raise DocumentError(f"Unsupported file type .{ext}. Supported: {', '.join(SUPPORTED_TYPES)}.")
    if ext == "pdf":
        text = _pdf_text(data)
    elif ext == "docx":
        text = _docx_text(data)
    elif ext in ("html", "htm"):
        text = _html_text(data)
    elif ext == "json":
        raw = _decode(data)
        try:
            text = json.dumps(json.loads(raw), indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            text = raw
    else:
        text = _decode(data)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise DocumentError("No readable text found in this file (scanned PDFs need OCR first).")
    return text


def chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Paragraph-aware chunks of roughly `size` characters with a small overlap."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        while len(p) > size:  # very long paragraph: hard split
            head, p = p[:size], p[size - overlap:]
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(head)
        if len(cur) + len(p) + 2 <= size:
            cur = f"{cur}\n\n{p}" if cur else p
        else:
            if cur:
                chunks.append(cur)
            tail = cur[-overlap:] if cur else ""
            cur = f"{tail} {p}".strip() if tail else p
    if cur:
        chunks.append(cur)
    return chunks


# ---------------------------------------------------------------- storage + index

def _collection():
    import chromadb
    from chromadb.config import Settings

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
    return client.get_or_create_collection(name=DOC_COLLECTION_NAME, metadata={"hnsw:space": "cosine"})


def _safe_name(name: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name).strip("._") or "document"
    return base[:120]


def _text_path(doc_id: int) -> Path:
    return DOCS_DIR / f"{doc_id}.extracted.txt"


def add_document(filename: str, data: bytes, *, title: str | None = None, collection: str = "General",
                 tags: list[str] | None = None, actor: str | None = None) -> int:
    if len(data) > MAX_BYTES:
        raise DocumentError("File is larger than 25 MB.")
    text = extract_text(filename, data)
    chunks = chunk_text(text)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    stored = DOCS_DIR / f"{uuid.uuid4().hex[:8]}_{_safe_name(filename)}"
    stored.write_bytes(data)
    ext = Path(filename).suffix.lower().lstrip(".")
    stem = re.sub(r"[_-]+", " ", Path(filename).stem).strip()
    doc_title = (title or "").strip() or (stem[:1].upper() + stem[1:]) or "Untitled"
    doc_id = execute(
        """
        INSERT INTO documents (title, filename, stored_path, collection, tags, file_type, size_bytes, char_count, chunk_count, uploaded_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (doc_title, Path(filename).name, str(stored), (collection or "General").strip() or "General",
         ", ".join(t.strip() for t in (tags or []) if t.strip()), ext, len(data), len(text), actor),
    )
    _text_path(doc_id).write_text(text, encoding="utf-8")
    try:
        _index(doc_id, doc_title, chunks)
    except Exception:
        delete_document(doc_id, actor=None, log=False)
        raise
    execute("UPDATE documents SET chunk_count = ? WHERE id = ?", (len(chunks), doc_id))
    log_activity("document", f"Uploaded “{doc_title}” to {collection or 'General'}",
                 ref_type="document", ref_id=doc_id, actor=actor)
    return doc_id


def _index(doc_id: int, title: str, chunks: list[str]) -> None:
    from .retrieval import embed_texts

    col = _collection()
    for start in range(0, len(chunks), 64):
        batch = chunks[start:start + 64]
        col.upsert(
            ids=[f"doc{doc_id}_c{start + i}" for i in range(len(batch))],
            embeddings=embed_texts(batch),
            documents=batch,
            metadatas=[{"doc_id": doc_id, "chunk": start + i, "title": title} for i in range(len(batch))],
        )


def list_documents(*, collection: str | None = None, q: str | None = None) -> list[dict]:
    where, params = [], []
    if collection:
        where.append("collection = ?")
        params.append(collection)
    if q:
        where.append("(title LIKE ? OR filename LIKE ? OR tags LIKE ?)")
        params += [f"%{q}%"] * 3
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    return fetchall(f"SELECT * FROM documents {clause} ORDER BY uploaded_at DESC, id DESC", tuple(params))


def collections() -> list[dict]:
    return fetchall("SELECT collection, COUNT(*) AS n FROM documents GROUP BY collection ORDER BY collection")


def get_document(doc_id: int) -> dict | None:
    return fetchone("SELECT * FROM documents WHERE id = ?", (doc_id,))


def document_text(doc_id: int) -> str:
    p = _text_path(doc_id)
    if p.exists():
        return p.read_text(encoding="utf-8")
    doc = get_document(doc_id)
    if not doc or not Path(doc["stored_path"]).exists():
        raise DocumentError("The stored file for this document is missing.")
    return extract_text(doc["filename"], Path(doc["stored_path"]).read_bytes())


def document_bytes(doc_id: int) -> bytes:
    doc = get_document(doc_id)
    if not doc or not Path(doc["stored_path"]).exists():
        raise DocumentError("The stored file for this document is missing.")
    return Path(doc["stored_path"]).read_bytes()


def update_document(doc_id: int, *, title: str, collection: str, tags: str, actor: str | None = None) -> None:
    execute("UPDATE documents SET title = ?, collection = ?, tags = ? WHERE id = ?",
            (title.strip() or "Untitled", collection.strip() or "General", tags.strip(), doc_id))
    try:  # keep the title shown in search results in sync
        col = _collection()
        got = col.get(where={"doc_id": doc_id})
        if got["ids"]:
            col.update(ids=got["ids"], metadatas=[{**m, "title": title.strip()} for m in got["metadatas"]])
    except Exception:
        pass
    log_activity("document", f"Updated details of “{title.strip()}”", ref_type="document",
                 ref_id=doc_id, actor=actor)


def delete_document(doc_id: int, actor: str | None = None, log: bool = True) -> None:
    doc = get_document(doc_id)
    try:
        _collection().delete(where={"doc_id": doc_id})
    except Exception:
        pass
    if doc:
        for p in (Path(doc["stored_path"]), _text_path(doc_id)):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
    execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    if log and doc:
        log_activity("document", f"Deleted “{doc['title']}”", ref_type="document", ref_id=doc_id, actor=actor)


def search_documents(query: str, k: int = 8, collection: str | None = None) -> list[dict]:
    """Semantic search over document chunks (same MiniLM embeddings as the ticket KB)."""
    from .retrieval import embed_texts

    query = (query or "").strip()
    if not query:
        return []
    col = _collection()
    n = col.count()
    if n == 0:
        return []
    where = None
    if collection:
        ids = [d["id"] for d in list_documents(collection=collection)]
        if not ids:
            return []
        where = {"doc_id": {"$in": ids}} if len(ids) > 1 else {"doc_id": ids[0]}
    res = col.query(query_embeddings=embed_texts([query]), n_results=min(k, n), where=where,
                    include=["documents", "metadatas", "distances"])
    docs = {d["id"]: d for d in list_documents()}
    hits = []
    for text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        d = docs.get(int(meta.get("doc_id", -1)))
        if not d:
            continue
        hits.append({
            "doc_id": d["id"], "title": d["title"], "collection": d["collection"], "file_type": d["file_type"],
            "chunk": int(meta.get("chunk", 0)), "text": text,
            "similarity": max(0.0, min(1.0, 1.0 - float(dist))),
        })
    return hits


# ---------------------------------------------------------------- summaries

_SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


def extractive_summary(text: str, n_sentences: int = 5) -> list[str]:
    """Pick the sentences most central to the document (TF-IDF cosine to the whole text)."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    sents = []
    for line in re.split(r"\n+", text):  # headings and list items end at a line break
        sents += [s.strip() for s in _SENT_RE.split(re.sub(r"\s+", " ", line)) if 25 <= len(s.strip()) <= 600]
    if len(sents) <= n_sentences:
        return sents
    vec = TfidfVectorizer(stop_words="english")
    try:
        m = vec.fit_transform(sents + [" ".join(sents)])
    except ValueError:
        return sents[:n_sentences]
    scores = cosine_similarity(m[:-1], m[-1]).ravel()
    top = sorted(sorted(range(len(sents)), key=lambda i: -scores[i])[:n_sentences])
    return [sents[i] for i in top]


def summarize(doc_id: int) -> dict:
    """LLM summary when a provider is configured, otherwise an extractive one. Never invented."""
    from .llm import complete, provider_name

    doc = get_document(doc_id)
    if not doc:
        raise DocumentError("Document not found.")
    text = document_text(doc_id)
    if provider_name():
        prompt = ("Summarize this internal document for a new employee in 5 short bullet points. "
                  "Use only facts stated in the document.\n\n"
                  f"TITLE: {doc['title']}\n\nDOCUMENT:\n{text[:12000]}")
        out = complete(prompt)
        if out:
            return {"method": provider_name(), "summary": out, "sentences": []}
    sents = extractive_summary(text)
    return {"method": "extractive", "summary": None, "sentences": sents}
