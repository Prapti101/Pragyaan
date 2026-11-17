"""Environment + thresholds for the Onboarding Knowledge Copilot."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
# Groq retired the Llama 3.x models on 16 Aug 2026 (console.groq.com/docs/deprecations); an older .env that still
# names one is moved to Groq's recommended replacement automatically.
GROQ_RETIRED: dict[str, str] = {
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "llama3-70b-8192": "openai/gpt-oss-120b",
    "llama3-8b-8192": "openai/gpt-oss-20b",
    "qwen/qwen3-32b": "openai/gpt-oss-120b",
    "qwen/qwen3.6-27b": "qwen/qwen3.8-27b",
    "meta-llama/llama-4-scout-17b-16e-instruct": "openai/gpt-oss-120b",
    "meta-llama/llama-4-maverick-17b-128e-instruct": "openai/gpt-oss-120b",
    "moonshotai/kimi-k2-instruct-0905": "openai/gpt-oss-120b",
}
_groq_model = (os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b").strip()
GROQ_MODEL: str = GROQ_RETIRED.get(_groq_model, _groq_model)
SIM_THRESHOLD: float = float(os.getenv("SIM_THRESHOLD", "0.55"))
CHROMA_DIR: Path = Path(os.getenv("CHROMA_DIR", str(ROOT / "data" / "chroma")))
SQLITE_PATH: Path = Path(os.getenv("SQLITE_PATH", str(ROOT / "data" / "copilot.db")))
EMBEDDING_MODEL: str = os.getenv(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
TOP_K: int = int(os.getenv("TOP_K", "5"))

DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"
EVAL_DIR = ROOT / "eval"
EVAL_RESULTS = EVAL_DIR / "results"

TICKETS_CSV = DATA_RAW / "dataset-tickets-multi-lang-4-20k.csv"
TICKETS_PARQUET = DATA_PROCESSED / "tickets_en.parquet"
TRAIN_PARQUET = DATA_PROCESSED / "train.parquet"
VAL_PARQUET = DATA_PROCESSED / "val.parquet"
TEST_PARQUET = DATA_PROCESSED / "test.parquet"

SEVERITY_MODEL_PATH = MODELS_DIR / "severity.joblib"
INTENT_MODEL_PATH = MODELS_DIR / "intent.joblib"
TFIDF_PATH = MODELS_DIR / "tfidf.joblib"
INTENT_TFIDF_PATH = MODELS_DIR / "intent_tfidf.joblib"

COLLECTION_NAME = "tickets_kb"

# Knowledge Hub (uploaded documents): files on disk + their own Chroma collection
DOCS_DIR: Path = Path(os.getenv("DOCS_DIR", str(ROOT / "data" / "documents")))
DOC_COLLECTION_NAME = "documents_kb"
# A question vs. a document passage scores lower than question vs. question,
# so the assistant uses its own cutoff for "this passage answers it".
DOC_SIM_THRESHOLD: float = float(os.getenv("DOC_SIM_THRESHOLD", "0.45"))
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# Severity routing thresholds (score = P(medium)*0.5 + P(high)*1.0)
URGENT_THRESHOLD = 0.70
NORMAL_THRESHOLD = 0.40
