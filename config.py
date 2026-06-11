"""
Application constants, paths, and backend selection.
All configurable values live here. No other module hardcodes paths or strings.

Override at runtime via environment variables:
    WHISPER_MODEL=small python main.py
    TRANSCRIPTION_BACKEND=openai python main.py
"""
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR       = Path(__file__).parent
DATA_DIR       = BASE_DIR / "data"
RECORDINGS_DIR = DATA_DIR / "recordings"
MODELS_DIR     = DATA_DIR / "models"
DB_PATH        = str(DATA_DIR / "sessions.db")

# ---------------------------------------------------------------------------
# Speech-to-Text
# ---------------------------------------------------------------------------

WHISPER_MODEL         = os.getenv("WHISPER_MODEL", "base")      # tiny | base | small
TRANSCRIPTION_BACKEND = os.getenv("TRANSCRIPTION_BACKEND", "local")   # local | openai (future)

# ---------------------------------------------------------------------------
# Coaching LLM
# ---------------------------------------------------------------------------

COACHING_BACKEND  = os.getenv("COACHING_BACKEND", "local")      # local | claude | openai (future)
LLAMA_MODEL_PATH  = os.getenv("LLAMA_MODEL_PATH", str(MODELS_DIR / "model.gguf"))

# ---------------------------------------------------------------------------
# API keys (only needed for cloud backends)
# ---------------------------------------------------------------------------

OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")