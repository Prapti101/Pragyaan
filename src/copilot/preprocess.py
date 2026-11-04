"""Text cleaning helpers for tickets and queries."""

from __future__ import annotations

import re

_PLACEHOLDER_RE = re.compile(
    r"<(?:tel_num|email|url|account_num|order_num|ip|date|name|address|"
    r"password|username|phone|amount|id)[^>]*>",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def build_ticket_text(subject: str | None, body: str | None) -> str:
    """Combine subject + body into a single searchable string."""
    subj = (subject or "").strip()
    bod = (body or "").strip()
    if subj and bod:
        return f"{subj}. {bod}"
    return subj or bod


def clean_text(text: str, strict: bool = False) -> str:
    """
    Light clean (default): strip placeholders, collapse whitespace.
    Strict: also lowercase — used for TF-IDF features.
    """
    if not text:
        return ""
    out = _PLACEHOLDER_RE.sub(" ", text)
    out = _WHITESPACE_RE.sub(" ", out).strip()
    if strict:
        out = out.lower()
    return out


_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has", "had", "are", "was", "were", "been",
    "but", "not", "can", "cannot", "can't", "cant", "could", "would", "should", "will", "your", "you", "our",
    "their", "they", "them", "what", "when", "where", "which", "who", "why", "how", "any", "all", "some",
    "into", "onto", "about", "there", "here", "its", "it's", "too", "very", "just", "also", "please",
    "help", "need", "want", "able", "getting", "get", "got", "does", "did", "doing", "is", "be", "of",
    "to", "in", "on", "at", "by", "an", "or", "as", "if", "my", "me", "we", "us", "i", "a", "it", "so",
    "ticket", "tickets", "issue", "issues", "problem", "problems",
}


def search_keywords(query: str, max_words: int = 8) -> list[str]:
    """Meaningful words from a search box query (lower-case, no stop words, 3+ characters)."""
    words = re.findall(r"[a-z0-9][a-z0-9'_-]*", (query or "").lower())
    seen, out = set(), []
    for w in words:
        w = w.strip("'-_")
        if len(w) >= 3 and w not in _STOPWORDS and w not in seen:
            seen.add(w)
            out.append(w)
    return out[:max_words]


def matched_keywords(words: list[str], text: str) -> list[str]:
    """Which query words occur in `text` at the start of a word ("pay" matches "payment", not "repay")."""
    low = (text or "").lower()
    return [w for w in words if re.search(r"(?<![a-z0-9])" + re.escape(w), low)]


def enough_keywords(matched: list[str], words: list[str]) -> bool:
    """A word-only match needs at least half of the query's meaningful words."""
    return bool(words) and len(matched) >= max(1, (len(words) + 1) // 2)
