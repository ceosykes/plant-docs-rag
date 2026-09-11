"""Every tunable, in one place, each with the reason it is that value.

Does: read the environment with in-project defaults. Nothing here is a secret.
Does not: hold keys. Keys come from .env via python-dotenv at import time.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent

# Paths. All inside the project so the image and the laptop see the same tree.
RAW_DIR = ROOT / os.environ.get("APP_RAW_DIR", "data/raw")
MANIFEST_PATH = RAW_DIR / "manifest.csv"
STORE_DIR = ROOT / os.environ.get("APP_STORE_DIR", "store")
CHROMA_DIR = STORE_DIR / "chroma"
BM25_PATH = STORE_DIR / "bm25.json"
CHECKPOINT_DB = STORE_DIR / "checkpoints.sqlite"
MEMORY_DB = STORE_DIR / "memory.sqlite"
RUNS_DIR = ROOT / "runs"
CHARTS_DIR = ROOT / "charts"
PROMPTS_DIR = ROOT / "app" / "graph" / "prompts"

# The three bodies. The router may pick any subset; the ingest tags every chunk with one.
CORPORA = ("safety", "maintenance", "quality")

# Model. One setting for all four agents; the user said Sonnet 5 at the dictation gate.
MODEL = os.environ.get("APP_MODEL", "claude-sonnet-5")
MODEL_TIMEOUT_S = 60.0     # a specialist call over 60s means retrieval handed it too much
MODEL_MAX_TOKENS = 4000    # findings are short; long output means the model is padding
EFFORT_ROUTER = "low"      # a three-way label; thinking hard here only adds latency
EFFORT_SPECIALIST = "medium"
EFFORT_CUSTOMER = "low"

# Chunking. Swept in phase 7 on a 177-page in-memory subset; the evidence sits beside each value.
CHUNK_SIZE = 1200   # page hit 0.89 at 1200 on a 177-page subset, 426 chunks; grid 400..1600 spans 0.89..0.94, within one question; chunk count 334..1476
CHUNK_OVERLAP = 150   # page hit 0.89 at 150 on a 177-page subset, 426 chunks; grid 0..300 spans 0.89..0.89, within one question; chunk count 407..459

# Retrieval. Swept in phase 7 on the full store against the golden set.
TOP_K = 8   # page hit 0.78 at k=8 on the golden set, 0.67 at 6; the curve flattens after 8, k=15 reaches 0.83 for far more chunks
DENSE_WEIGHT = 0.5   # page hit 0.67 at 0.5; BM25 alone 0.56, dense alone 0.61; best point 0.25 at 0.67
CHROMA_SPACE = "cosine"   # PROOF: stored vector norms are 1.0, so cosine, l2 and ip rank identically (l2 = 2 x cosine distance, same order on 200 chunks); cosine because 0..2 reads as a similarity
COLLECTION = "plant_docs"

# Guardrails. These strings are what the model must emit; code matches on them exactly.
REFUSAL_STRING = "NOT_IN_MY_DOCUMENTS"
ESCALATION_TEXT = (
    "I could not find this in the safety, maintenance or quality documents. "
    "I have sent this to your manager. Check the manual for now and do not start "
    "the job until they answer."
)
FORBIDDEN_PATTERNS = (
    "lockout is not needed", "no lockout needed", "safe to run", "you can skip",
    "skip the lockout", "lot is accepted", "lot passes",
)
MEMORY_MAX_ITEMS = 3       # past decisions fed as context; more than three reads as noise

# API.
API_PORT = int(os.environ.get("PORT", "8020"))
ALLOWED_ORIGINS = [o for o in os.environ.get("APP_ALLOWED_ORIGINS", "http://localhost:5199").split(",") if o]
INTERNAL_TOKEN = os.environ.get("APP_INTERNAL_TOKEN", "")
