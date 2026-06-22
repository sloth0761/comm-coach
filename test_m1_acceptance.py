"""
PRD §17 functional acceptance check — run the real pipeline against a
representative ~5-minute recording and measure the two criteria that can't
be checked by code inspection: end-to-end time and peak RAM.

Run from project root: python test_m1_acceptance.py
Requires data/recordings/_synthetic_5min.wav (built by concatenating real
speech clips — see conversation).
"""
from __future__ import annotations

import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import resource
import sys
import time
import wave
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

WAV_PATH = "data/recordings/_synthetic_5min.wav"
TARGET_S = 60.0


def main() -> None:
    import config
    from core.contracts import RecordingResult
    from core.memory import MemoryStore
    from core.memory_engine import MemoryEngine
    from core.transcriber import make_transcriber
    from core.analyzer import make_coach
    from core.embedder import Embedder
    from core.pipeline import SessionPipeline

    w = wave.open(WAV_PATH)
    duration = w.getnframes() / w.getframerate()
    w.close()
    print(f"input: {WAV_PATH} ({duration:.1f}s)")

    store = MemoryStore(config.DB_PATH)
    pipeline = SessionPipeline(
        transcriber=make_transcriber(config),
        coach=make_coach(config),
        store=store,
        engine=MemoryEngine(store),
        embedder=Embedder(config.EMBEDDING_MODEL),
        on_stage=lambda s: print(f"  [{time.time()-t0:6.1f}s] {s.value}"),
    )

    recording = RecordingResult(
        wav_path=WAV_PATH, duration_seconds=duration, created_at=datetime.now(),
    )

    t0 = time.time()
    result = pipeline.run(recording)
    elapsed = time.time() - t0

    peak_rss_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # bytes on macOS
    peak_gb = peak_rss_bytes / (1024 ** 3)

    print()
    print(f"session_id      = {result.session_id}")
    print(f"elapsed         = {elapsed:.1f}s  (target < {TARGET_S:.0f}s)  -> {'PASS' if elapsed < TARGET_S else 'FAIL'}")
    print(f"peak RSS        = {peak_gb:.2f} GB  (target < 1.5 GB)        -> {'PASS' if peak_gb < 1.5 else 'FAIL'}")


if __name__ == "__main__":
    main()
