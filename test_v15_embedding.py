"""
Regression check: core/embedder.py's SentenceTransformer.encode() deadlocks
(0% CPU, never returns) when it runs in the same process *after*
faster-whisper and llama-cpp-python have already initialized their own
native thread pools — three OpenMP/threading runtimes contending.

main.py works around this with KMP_DUPLICATE_LIB_OK=TRUE (avoids the
SIGABRT crash) and OMP_NUM_THREADS=1 (avoids the deadlock). This test
reproduces the real load order and fails loudly instead of hanging forever
if either workaround regresses.

Run from project root: python test_v15_embedding.py
"""
from __future__ import annotations

import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

TIMEOUT_S = 30


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        sys.exit(1)


def main() -> None:
    import config
    import gc

    print("loading whisper...")
    from faster_whisper import WhisperModel
    m = WhisperModel("base", device="cpu", compute_type="int8")
    del m
    gc.collect()

    print("loading llama...")
    from llama_cpp import Llama
    llm = Llama(model_path=config.LLAMA_MODEL_PATH, n_ctx=512,
                n_threads=os.cpu_count() or 4, verbose=False)
    del llm
    gc.collect()

    print(f"embedding (deadlocks without the fix — {TIMEOUT_S}s timeout)...")
    from core.embedder import Embedder
    result: dict = {}

    def _embed():
        result["vec"] = Embedder().embed("hello world this is a test")

    t = threading.Thread(target=_embed, daemon=True)
    t.start()
    t.join(timeout=TIMEOUT_S)

    check("embed() returned within timeout (no deadlock)", not t.is_alive())
    check("embedding has 384 dims", result.get("vec") is not None and result["vec"].shape == (384,))

    print("\n✓  All tests passed.")


if __name__ == "__main__":
    main()
