"""Intent (ticket type) classifier."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import joblib

from .config import INTENT_MODEL_PATH
from .preprocess import clean_text


@lru_cache(maxsize=1)
def _load() -> Any:
    if not INTENT_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Intent model missing. Run scripts/train_intent.py first.\n"
            f"Expected: {INTENT_MODEL_PATH}"
        )
    return joblib.load(INTENT_MODEL_PATH)


def predict_intent(question: str) -> str:
    pipe = _load()
    text = clean_text(question, strict=True)
    return str(pipe.predict([text])[0])


def intent_probabilities(question: str) -> dict[str, float]:
    """Probability for every ticket type (used by the Model Comparison page)."""
    pipe = _load()
    text = clean_text(question, strict=True)
    if hasattr(pipe, "predict_proba"):
        proba = pipe.predict_proba([text])[0]
        return {str(c): float(p) for c, p in zip(pipe.classes_, proba)}
    return {str(pipe.predict([text])[0]): 1.0}
