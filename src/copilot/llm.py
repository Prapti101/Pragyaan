"""LLM provider wrapper (Groq / Gemini) with local fallback.

Every call records why it failed (rate limit, daily limit, bad key, network ...) so the interface can say
"the language model is unavailable right now" instead of pretending an answer was generated. When the main
Groq model is rate limited, the call is retried once on a smaller Groq model that has its own limits.
"""

from __future__ import annotations

import hashlib
import os

from .config import GEMINI_API_KEY, GEMINI_MODEL, GROQ_API_KEY, GROQ_MODEL, GROQ_RETIRED

# Smaller Groq model used for query rewriting and as a fallback when the main model is rate limited.
# Set GROQ_FALLBACK_MODEL= (empty) in .env to switch the fallback off.
_fb = os.getenv("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b").strip()
GROQ_FALLBACK_MODEL: str = GROQ_RETIRED.get(_fb, _fb)
# When Groq says a configured model doesn't exist (retired), the first of these that the account can use is taken.
_GROQ_PREFERRED = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
_SWAPPED: dict[str, str | None] = {}  # retired model -> model found to replace it (None: none found)


def _groq_kwargs(model: str, max_tokens: int) -> dict:
    """Per-model request options: GPT-OSS models reason before answering; keep that short and out of the reply."""
    if model.startswith("openai/gpt-oss"):
        return {"max_tokens": max_tokens + 600, "extra_body": {"reasoning_effort": "low", "include_reasoning": False}}
    return {"max_tokens": max_tokens}


def _replacement(client, model: str) -> str | None:
    """A model this API key can use instead of a retired one (asks Groq which models exist; cached)."""
    if model in _SWAPPED:
        return _SWAPPED[model]
    choice = None
    try:
        ids = {m.id for m in client.models.list().data}
        choice = next((m for m in _GROQ_PREFERRED if m in ids and m != model), None) or next(
            (m for m in sorted(ids) if ("gpt-oss" in m or "qwen" in m or "llama" in m)
             and "guard" not in m and "whisper" not in m and m != model), None)
    except Exception as e:  # noqa: BLE001
        print(f"[llm] could not list Groq models: {type(e).__name__}")
    _SWAPPED[model] = choice
    if choice:
        print(f"[llm] Groq model {model} is not available; using {choice} instead")
    return choice


def _groq_models(fast: bool = False) -> list[str]:
    models = [GROQ_MODEL]
    if GROQ_FALLBACK_MODEL and GROQ_FALLBACK_MODEL != GROQ_MODEL:
        models = [GROQ_FALLBACK_MODEL, GROQ_MODEL] if fast else [GROQ_MODEL, GROQ_FALLBACK_MODEL]
    return [_SWAPPED.get(m) or m for m in models]

_CACHE: dict[str, str] = {}
_LAST_ERROR: str | None = None
_LAST_MODEL: str | None = None

GROUNDED_PROMPT = """You help an employee fix a work problem, using ONLY the past support tickets below
(each has the original problem Q and the support team's reply A).

How to answer:
- Read ALL the tickets, not just the first one, and combine what they say into one practical answer for the
  employee's exact problem.
- Start with one sentence naming the likely cause or what is going on.
- Then give 3 to 6 numbered steps the employee can try now, in a sensible order. Each step must come from the
  tickets (something support told people to do, or something that fixed or was tried for the same problem).
  Put the source after each step as [ticket_id].
- End with one line starting "If it still fails:" saying what details to send to support, based on what the
  replies ask for (error message, screenshots, device, when it started ...).
- Skip greetings, apologies, placeholders such as [Name] or <acc_num>, and requests for a callback.
- Do not add steps, products, links or numbers that are not in the tickets.
- If the tickets are about a different problem and do not help with this one, reply exactly: NO_ANSWER

PAST TICKETS:
{context}

EMPLOYEE'S PROBLEM: {question}
"""

EXPAND_PROMPT = """Rewrite this short message from an employee as an IT/HR support ticket: a short subject line,
then one or two sentences describing the same problem in standard support wording.
Keep exactly the same problem. Do not add causes, product names, error codes or details that are not implied.
Plain text only, no labels, no quotes.

MESSAGE: {message}"""


def _cache_key(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def build_prompt(question: str, context: str) -> str:
    return GROUNDED_PROMPT.format(context=context, question=question)


def _reason(e: Exception) -> str:
    """Short, human reason for a provider failure (never includes the key)."""
    msg, name = str(e).lower(), type(e).__name__.lower()
    status = getattr(e, "status_code", None)
    if "per day" in msg or "tokens per day" in msg or "tpd" in msg or "requests per day" in msg:
        return "daily usage limit reached"
    if status == 429 or "ratelimit" in name or "rate limit" in msg or "rate_limit" in msg:
        return "rate limit reached, try again in a minute"
    if status == 413 or "too large" in msg:
        return "request too large for the current limit"
    if status in (401, 403) or "invalid api key" in msg or "authentication" in name:
        return "API key rejected"
    if status == 404 or "decommissioned" in msg or "model_not_found" in msg or "does not exist" in msg:
        return "model not available"
    if "connect" in msg or "timeout" in msg or "connection" in name or "timeout" in name:
        return "no connection to the provider"
    return "provider error"


def _groq_once(prompt: str, model: str, max_tokens: int, _retry: bool = True) -> str | None:
    global _LAST_ERROR, _LAST_MODEL
    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY, max_retries=1, timeout=45)
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a concise, factual onboarding knowledge assistant."},
                {"role": "user", "content": prompt},
            ],
            model=model,
            temperature=0.1,
            **_groq_kwargs(model, max_tokens),
        )
        text = (chat_completion.choices[0].message.content or "").strip()
        if text:
            _LAST_ERROR, _LAST_MODEL = None, f"Groq ({model})"
        return text or None
    except Exception as e:  # noqa: BLE001 - any provider failure falls back
        _LAST_ERROR = _reason(e)
        print(f"[llm] Groq ({model}) call failed: {_LAST_ERROR}: {type(e).__name__}")
        if _LAST_ERROR == "model not available" and _retry:
            other = _replacement(client, model)
            if other:
                return _groq_once(prompt, other, max_tokens, _retry=False)
        return None


def _call_groq(prompt: str, *, fast: bool = False, max_tokens: int = 700) -> str | None:
    """Main model first (or the small model first when fast=True); the other one if that fails."""
    if not GROQ_API_KEY:
        return None
    for model in _groq_models(fast):
        text = _groq_once(prompt, model, max_tokens)
        if text:
            return text
        # a bad key fails the same way on every model
        if _LAST_ERROR == "API key rejected":
            break
    return None


def _call_gemini(prompt: str) -> str | None:
    global _LAST_ERROR, _LAST_MODEL
    if not GEMINI_API_KEY:
        return None
    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)
        resp = model.generate_content(prompt)
        text = (resp.text or "").strip()
        if text:
            _LAST_ERROR, _LAST_MODEL = None, f"Gemini ({GEMINI_MODEL})"
        return text or None
    except Exception as e:  # noqa: BLE001
        _LAST_ERROR = _reason(e)
        print(f"[llm] Gemini call failed: {_LAST_ERROR}: {type(e).__name__}")
        return None


def _complete_raw(prompt: str, *, fast: bool = False, max_tokens: int = 700) -> tuple[str | None, str | None]:
    """(text, model label) from the first provider that answers; (None, None) when none does."""
    text = _call_groq(prompt, fast=fast, max_tokens=max_tokens) if GROQ_API_KEY else None
    if text is None and GEMINI_API_KEY:
        text = _call_gemini(prompt)
    return (text, _LAST_MODEL) if text else (None, None)


def generate_ex(question: str, context: str, fallback_answer: str | None = None) -> tuple[str, str | None]:
    """Grounded generation → (text, method).

    method names the model that wrote the answer, or is None when no model answered and the closest past
    answer is returned verbatim (or NO_ANSWER when there is none). Fallbacks are never cached, so the next
    question tries the model again.
    """
    prompt = build_prompt(question, context)
    key = _cache_key(prompt)
    if key in _CACHE:
        text, _, method = _CACHE[key].partition("\x00")
        return text, method or provider_name()

    text, method = _complete_raw(prompt)
    if text is not None:
        _CACHE[key] = f"{text}\x00{method or ''}"
        return text, method
    if fallback_answer and fallback_answer.strip():
        return fallback_answer.strip(), None
    return "NO_ANSWER", None


def generate(question: str, context: str, fallback_answer: str | None = None) -> str:
    """Grounded generation (text only). See generate_ex."""
    return generate_ex(question, context, fallback_answer)[0]


def expand_query(message: str) -> str | None:
    """A fuller, ticket-style wording of a short message, used only to search (never shown as an answer).

    Short messages ("I forgot my password") score low against long ticket texts even when they describe the
    same problem; searching with this rewording as well finds those tickets. None when no model is available.
    """
    m = (message or "").strip()
    if not m or not provider_name():
        return None
    prompt = EXPAND_PROMPT.format(message=m[:400])
    key = "expand:" + _cache_key(prompt)
    if key in _CACHE:
        return _CACHE[key]
    text, _ = _complete_raw(prompt, fast=True, max_tokens=120)
    if not text or is_no_answer(text):
        return None
    text = " ".join(text.replace('"', " ").split())[:600]
    _CACHE[key] = text
    return text


def chat_stream(messages: list[dict], *, max_tokens: int = 1200, temperature: float = 0.5):
    """Stream a conversational reply (OpenAI-style messages: system / user / assistant), chunk by chunk.

    Tries the main Groq model, then the smaller one, then Gemini. Yields nothing when no provider answers;
    last_error() then says why. If a reply breaks off midway, what arrived is kept and last_error() is set.
    """
    global _LAST_ERROR, _LAST_MODEL
    if GROQ_API_KEY:
        from groq import Groq

        models = _groq_models()
        client = Groq(api_key=GROQ_API_KEY, max_retries=1, timeout=60)
        tried: set[str] = set()
        while models:
            model = models.pop(0)
            if model in tried:
                continue
            tried.add(model)
            got = False
            try:
                stream = client.chat.completions.create(messages=messages, model=model, temperature=temperature,
                                                        stream=True, **_groq_kwargs(model, max_tokens))
                for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        if not got:
                            got, _LAST_ERROR, _LAST_MODEL = True, None, f"Groq ({model})"
                        yield delta
                if got:
                    return
            except Exception as e:  # noqa: BLE001
                _LAST_ERROR = _reason(e)
                print(f"[llm] Groq ({model}) chat failed: {_LAST_ERROR}: {type(e).__name__}")
                if got or _LAST_ERROR == "API key rejected":
                    return
                if _LAST_ERROR == "model not available":
                    other = _replacement(client, model)
                    if other and other not in tried:
                        models.insert(0, other)
    if GEMINI_API_KEY:
        flat = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages) + "\n\nASSISTANT:"
        text = _call_gemini(flat)
        if text:
            yield text


def last_model() -> str | None:
    """The model that answered the most recent successful call."""
    return _LAST_MODEL


def is_no_answer(text: str) -> bool:
    return text.strip().upper().startswith("NO_ANSWER")


def provider_name() -> str | None:
    """Which LLM provider is configured, or None (retrieval-only mode)."""
    if GROQ_API_KEY:
        return f"Groq ({_SWAPPED.get(GROQ_MODEL) or GROQ_MODEL})"
    if GEMINI_API_KEY:
        return f"Gemini ({GEMINI_MODEL})"
    return None


def last_error() -> str | None:
    """Why the most recent model call failed (None if it worked or no model is configured)."""
    return _LAST_ERROR if provider_name() else None


def complete(prompt: str) -> str | None:
    """Free-form completion for summaries/assistant. None when no provider works.

    Never fabricates: callers must fall back to a retrieval/extractive answer. Only successes are cached.
    """
    key = "complete:" + _cache_key(prompt)
    if key in _CACHE:
        return _CACHE[key]
    text, _ = _complete_raw(prompt)
    if text:
        _CACHE[key] = text
    return text
