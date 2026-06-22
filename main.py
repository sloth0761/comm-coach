"""
main.py

Comm Coach application entry point.
"""
from __future__ import annotations

import logging
import os
import sys

# faster-whisper's backend (ctranslate2) and PyTorch (pulled in by
# sentence-transformers for v1.5 embeddings) each bundle their own OpenMP
# runtime. Loading both into one process aborts with "OMP: Error #15"
# even though the two are never used concurrently — dlopen'd native libs
# stay mapped for the process lifetime regardless of Python-level
# load/free discipline. Must be set before either library is imported.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# Avoids a network round-trip to HF Hub on every embedding call (Stage 5b
# reloads SentenceTransformer from scratch each time) — the model is already
# cached after first download, so force cache-only lookups.
os.environ.setdefault("HF_HUB_OFFLINE", "1")

# Without this, torch deadlocks (0% CPU, never returns) inside
# SentenceTransformer.encode() when it runs after faster-whisper and
# llama-cpp-python have already initialized their own native thread pools
# in this process — three OpenMP/threading runtimes contending. Reproduced
# directly: encode() hangs indefinitely with OMP_NUM_THREADS unset, returns
# in ~1s with it pinned to 1. The model is tiny (384-dim MiniLM, one short
# text per call) so single-threaded costs nothing measurable.
os.environ.setdefault("OMP_NUM_THREADS", "1")


def main() -> None:
    import config
    for d in (config.DATA_DIR, config.RECORDINGS_DIR, config.MODELS_DIR):
        os.makedirs(str(d), exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL if hasattr(config, "LOG_LEVEL") else "INFO"),
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    )

    from core.memory        import MemoryStore
    from core.memory_engine import MemoryEngine
    from core.transcriber   import make_transcriber
    from core.analyzer      import make_coach
    from core.pipeline      import SessionPipeline

    store       = MemoryStore(config.DB_PATH)
    engine      = MemoryEngine(store)
    transcriber = make_transcriber(config)
    coach       = make_coach(config)

    embedder = None
    if getattr(config, "EMBEDDING_BACKEND", "local") == "local":
        try:
            from core.embedder import Embedder
            embedder = Embedder(config.EMBEDDING_MODEL)
            logging.getLogger(__name__).info("Embedder ready: %s", config.EMBEDDING_MODEL)
        except Exception as exc:
            logging.getLogger(__name__).warning("Embedder unavailable (%s). Recency fallback active.", exc)

    pipeline = SessionPipeline(
        transcriber=transcriber,
        coach=coach,
        store=store,
        engine=engine,
        embedder=embedder,
    )

    from PyQt6.QtWidgets import QApplication
    from ui.app   import MainWindow
    from ui.theme import STYLESHEET

    app = QApplication(sys.argv)
    app.setApplicationName("Comm Coach")
    app.setStyleSheet(STYLESHEET)

    window = MainWindow(pipeline=pipeline, store=store)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
