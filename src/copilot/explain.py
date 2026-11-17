"""Explainability layer: why an answer or a recommended solution was chosen, how close the match is,
and why a question went to a Senior Analyst.

The numbers always come from the system itself: the similarity search (how close two texts are in meaning,
shown as a percentage) and the priority model (its predicted class, probability and the words that drove
it). When a Groq or Gemini key is configured, the language model only turns those facts and the two texts
into plain sentences; it never changes a route, a score or a priority. Without a key, the same facts are
written out directly, so there is always an explanation and nothing is invented.
"""

from __future__ import annotations

import re
from .config import SIM_THRESHOLD
from .llm import complete, is_no_answer, last_error, provider_name
from .preprocess import matched_keywords, search_keywords

# ---------------------------------------------------------------- small talk and vague questions

_GREETING_RE = re.compile(
    r"^\s*(hi+|hello+|hey+|hiya|yo|namaste|hola|greetings|good\s+(morning|afternoon|evening|night)|"
    r"thanks?|thank\s+you|thx|ty|ok(ay)?|cool|great|nice|bye|goodbye|see\s+you|"
    r"who\s+are\s+you|what\s+are\s+you|what\s+can\s+you\s+do|how\s+are\s+you)\b",
    re.I,
)
# words that carry no support problem in a greeting ("hello gemini", "thanks assistant")
_CHAT_WORDS = {"hello", "hey", "hiya", "namaste", "hola", "greetings", "morning", "afternoon", "evening", "night",
               "thanks", "thank", "thx", "okay", "cool", "great", "nice", "bye", "goodbye", "see", "who", "are",
               "you", "what", "can", "do", "how", "assistant", "bot", "chatbot", "gemini", "groq", "grok",
               "chatgpt", "gpt", "claude", "pragyaan", "there", "team", "dear", "sir", "madam", "buddy", "friend",
               "doing", "today", "much", "lot", "again", "all", "everyone"}


def content_words(text: str) -> list[str]:
    """Meaningful words in a message (no stop words, greetings or assistant names)."""
    return [w for w in search_keywords(text, max_words=20) if w not in _CHAT_WORDS]


def is_small_talk(text: str) -> bool:
    """A greeting, a thank-you or a question about the assistant itself, with no support problem in it."""
    return bool(_GREETING_RE.match(text or "")) and len(content_words(text)) == 0


def is_too_vague(text: str) -> bool:
    """Too little to match reliably (e.g. one word). Such questions get a request for detail instead of an
    escalation when nothing matches."""
    return len(content_words(text)) < 2


_HELP_TEXT = ("I'm the PRAGYAAN assistant. Describe a work problem, for example “VPN disconnects every few "
              "minutes”, and I'll answer from your company's documents and thousands of solved tickets, with the "
              "sources and how closely they match. Type “summarize” and a document name to get its key points. "
              "If nothing matches, I'll pass your question to a Senior Analyst.")

_SMALL_TALK_PROMPT = """You are the PRAGYAAN support assistant inside a company's IT and HR help portal.
The employee wrote: "{message}"
Reply in at most two short, friendly sentences. Do not claim to be any other assistant or product.
Then add one sentence saying what you can do: answer work problems from the company's documents and solved
tickets (with sources and how closely they match), summarize a document when they type "summarize" and its name,
and pass anything unanswered to a Senior Analyst. Plain text only."""


def small_talk_reply(text: str) -> tuple[str, str | None]:
    """(reply, method). Uses the language model when one is configured, otherwise a fixed help message."""
    if provider_name():
        raw = _llm(_SMALL_TALK_PROMPT.format(message=(text or "").strip()[:300]))
        if raw and not is_no_answer(raw):
            return raw.strip(), provider_name()
    return _HELP_TEXT, None


def needs_detail_reply(text: str, best_similarity: float) -> str:
    pct = round(best_similarity * 100)
    return (f"Could you describe the problem in a bit more detail? For example what you were doing, what you "
            f"expected and any error message. “{(text or '').strip()[:60]}” is too short to match reliably "
            f"(the closest solved ticket is only {pct}% similar), so I haven't sent it to a Senior Analyst yet.")


# ---------------------------------------------------------------- match explanations

def match_level(similarity: float, threshold: float = SIM_THRESHOLD) -> str:
    if similarity >= threshold + 0.2:
        return "Very close match"
    if similarity >= threshold + 0.1:
        return "Close match"
    if similarity >= threshold:
        return "Good enough to suggest"
    return "Weak match"


def shared_terms(question: str, other: str, k: int = 6) -> list[str]:
    """Words from the question that also appear in the matched text."""
    return matched_keywords(search_keywords(question, max_words=14), other)[:k]


def _llm(prompt: str) -> str | None:
    """complete() caches successful replies only, so a failed call (e.g. a rate limit) is retried next time."""
    return complete(prompt)


_MATCH_PROMPT = """You explain to an employee why a {kind} was suggested for their problem.
Facts you must not change: the two texts are {pct}% similar in meaning (semantic similarity; {thr}% or more is
needed before anything is suggested). Words both texts share: {shared}.

THEIR PROBLEM:
{question}

SUGGESTED {kind_upper}:
{matched}

SOLUTION IT CONTAINS:
{answer}

Write two or three short sentences in plain English: what the two problems have in common and why this solution
should apply. Then write one line that starts with "Check:" and names one difference or assumption the employee
should verify before relying on it. Use only the texts above; do not invent product names, steps or numbers.
No headings, no bullet points, no markdown."""


def explain_match(question: str, matched_text: str | None, answer: str | None, similarity: float, *,
                  source: str, kind: str = "past ticket", threshold: float = SIM_THRESHOLD,
                  use_llm: bool = True) -> dict:
    """Why `matched_text` / `answer` was suggested for `question`.

    Returns pct (0-100), threshold_pct, level, shared words, a factual summary, and, when a language model
    is configured, `text`: a plain-language explanation with a "Check:" line (`method` names the model)."""
    similarity = max(0.0, min(1.0, float(similarity or 0)))
    pct, thr = round(similarity * 100), round(threshold * 100)
    shared = shared_terms(question, f"{matched_text or ''} {answer or ''}")
    level = match_level(similarity, threshold)
    words = ", ".join(f"“{w}”" for w in shared[:4])
    summary = (f"{level}: {pct}% similar in meaning to {source}; anything below {thr}% is not suggested. "
               + (f"Both mention {words}." if shared else
                  "They use different words for the same kind of problem, so the match is on meaning."))
    out = {"pct": pct, "threshold_pct": thr, "level": level, "shared": shared, "summary": summary,
           "text": None, "method": None, "source": source}
    if use_llm and provider_name():
        prompt = _MATCH_PROMPT.format(
            kind=kind, kind_upper=kind.upper(), pct=pct, thr=thr, shared=", ".join(shared) or "none",
            question=(question or "").strip()[:1500], matched=(matched_text or "(not available)").strip()[:1500],
            answer=(answer or "").strip()[:1500])
        raw = _llm(prompt)
        if raw and not is_no_answer(raw):
            out["text"], out["method"] = raw.strip(), provider_name()
        elif raw is None:
            out["llm_error"] = last_error() or "no reply"
    return out


# ---------------------------------------------------------------- the solution, in plain steps

_SOLUTION_PROMPT = """An employee has this problem:
{problem}

A very similar problem was solved before.
PAST PROBLEM: {past}
SUPPORT'S REPLY: {reply}

Write the solution for the employee as 2 to 4 short numbered steps they can follow now, using only the past problem
and support's reply. If the reply mostly asks for information (an account number, a good time for a callback,
screenshots, error messages, device details), make the last step "Send IT support ..." listing exactly what they asked
for. Do not add technical steps, products, links or numbers that are not in the texts. No greeting, no heading and no
formatting other than the numbered list. If the reply has nothing useful for this problem, reply exactly: NO_ANSWER"""


def solution_steps(problem: str, past_problem: str | None, reply: str, *, use_llm: bool = True) -> dict:
    """The matched ticket's solution as numbered steps for this employee's problem.

    Written by the language model from support's reply only (it may not add steps); without a model, or when the
    reply has nothing usable, the reply itself is shown. Returns text, method (model name or None) and llm_error."""
    reply = (reply or "").strip()
    out = {"text": reply, "method": None, "llm_error": None}
    if not (use_llm and reply and provider_name()):
        return out
    raw = _llm(_SOLUTION_PROMPT.format(problem=(problem or "").strip()[:800], past=(past_problem or "").strip()[:800],
                                       reply=reply[:1500]))
    if raw and not is_no_answer(raw):
        out["text"], out["method"] = raw.strip(), provider_name()
    elif raw is None:
        out["llm_error"] = last_error() or "no reply"
    return out


# ---------------------------------------------------------------- escalation explanations

_ESCALATION_PROMPT = """An employee's question could not be answered automatically and was sent to a Senior Analyst.
Facts you must not change: the closest solved ticket is {pct}% similar in meaning; {thr}% is needed to answer
automatically. The priority model (a Random Forest on the words of the question) rated it {label} priority,
{conf}% probability. The words that pushed it towards that rating were: {terms}.

QUESTION:
{question}

In two or three short sentences of plain English, explain why it was escalated and what the signal words suggest
about urgency. If the signal words say little about urgency, say that the priority is a low-confidence estimate a
Senior Analyst will review. Do not invent details. No headings, no bullet points, no markdown."""


def explain_escalation(question: str, best_similarity: float, severity: dict | None, *,
                       threshold: float = SIM_THRESHOLD, use_llm: bool = True) -> dict:
    sev = severity or {}
    label = str(sev.get("label") or "medium")
    terms = [t for t in (sev.get("top_terms") or []) if t]
    try:
        from .severity import severity_probabilities

        conf = severity_probabilities(question).get(label)
    except Exception:
        conf = None
    pct, thr = round(max(0.0, float(best_similarity or 0)) * 100), round(threshold * 100)
    conf_pct = round(conf * 100) if conf is not None else None
    reason = (f"The closest solved ticket is only {pct}% similar (an automatic answer needs {thr}%), so a Senior "
              f"Analyst will answer it.")
    prio = (f"The priority model rates it {label}" + (f" ({conf_pct}% probability)" if conf_pct is not None else "")
            + (f", mostly because of {', '.join(f'“{t}”' for t in terms[:4])}." if terms else "."))
    out = {"pct": pct, "threshold_pct": thr, "label": label, "confidence_pct": conf_pct, "terms": terms,
           "summary": f"{reason} {prio}", "text": None, "method": None}
    if use_llm and provider_name():
        raw = _llm(_ESCALATION_PROMPT.format(pct=pct, thr=thr, label=label, conf=conf_pct if conf_pct is not None else "unknown",
                                             terms=", ".join(terms) or "none", question=(question or "").strip()[:1500]))
        if raw and not is_no_answer(raw):
            out["text"], out["method"] = raw.strip(), provider_name()
        elif raw is None:
            out["llm_error"] = last_error() or "no reply"
    return out


__all__ = ["content_words", "is_small_talk", "is_too_vague", "small_talk_reply", "needs_detail_reply",
           "match_level", "shared_terms", "explain_match", "explain_escalation", "solution_steps"]
