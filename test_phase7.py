"""
Standalone validation for Phase 7: LocalLLMCoach + SmolLM2 inference.
Run from project root: python tests/test_phase7.py

T1–T7  fast (no model load).
T8–T9  run real inference — expect 20–60 s on a 2016 Intel MacBook Pro.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_TRANSCRIPT = (
    "Um basically I think the architecture we've chosen is solid. "
    "You know the five-stage pipeline makes it very clear where each "
    "responsibility lives. Actually I believe the memory engine is what "
    "makes this genuinely useful over time rather than just another "
    "analyser that forgets everything the moment you close it. "
    "I just wanted to make sure we have good test coverage before "
    "we move on to the UI phase of the project."
)

_GOOD_JSON = json.dumps({
    "overall_assessment": "Strong session with clear structure and good pacing.",
    "strengths": ["Clear articulation of technical concepts", "Good sentence variety"],
    "improvements": ["Reduce filler words like 'basically' and 'um'", "Cut verbose phrases"],
    "key_insight": "You use 'basically' as a hedge when introducing ideas.",
    "next_focus": "Record one minute without using 'basically' or 'um'.",
})

_FENCED_JSON = f"```json\n{_GOOD_JSON}\n```"
_BAD_JSON    = "Here is my feedback: the session was great!"
_MISSING_KEY = json.dumps({"overall_assessment": "Good.", "strengths": []})
_EMPTY_STR   = json.dumps({
    "overall_assessment": "",
    "strengths": [],
    "improvements": [],
    "key_insight": "ok",
    "next_focus": "ok",
})


def _make_context():
    from core.contracts import Dimension, MemoryContext
    from analytics import run_all
    from core.contracts import Segment, TranscriptionResult
    from analytics._text import tokenize

    tokens = tokenize(_TRANSCRIPT)
    tr = SimpleNamespace(
        text=_TRANSCRIPT,
        segments=(Segment(0.0, 20.0, _TRANSCRIPT, 0.83),),
        word_count=len(tokens),
        speaking_rate_wpm=145.0,
    )
    analytics = run_all(tr, 30.0)
    context = MemoryContext(
        recent_sessions=(),
        recurring_patterns=("overuses_filler (3 sessions)",),
        trends={str(d): "stable" for d in Dimension},
        rendered="CURRENT TRANSCRIPT\n" + _TRANSCRIPT + "\n\nCURRENT SCORES\nFluency: 62",
    )
    return analytics, context


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def run() -> None:

    print("\n── T1  llama_cpp importable ────────────────────────────")
    try:
        from llama_cpp import Llama
        check("llama_cpp imports", True)
    except ImportError as exc:
        print(f"  FAIL  {exc}")
        print("        pip install llama-cpp-python")
        sys.exit(1)


    print("\n── T2  Model file exists ───────────────────────────────")
    import config
    model_path = Path(config.LLAMA_MODEL_PATH)
    check("model.gguf exists",      model_path.exists(), str(model_path))
    check("model size > 100 MB",    model_path.stat().st_size > 100_000_000,
          f"{model_path.stat().st_size // 1_000_000} MB")


    print("\n── T3  make_coach returns LocalLLMCoach ────────────────")
    from core.analyzer import LocalLLMCoach, DummyCoach, make_coach

    cfg = SimpleNamespace(
        COACHING_BACKEND="local",
        LLAMA_MODEL_PATH=str(model_path),
    )
    coach = make_coach(cfg)
    check("returns LocalLLMCoach", isinstance(coach, LocalLLMCoach))


    print("\n── T4  _parse — valid JSON ──────────────────────────────")
    from core.analyzer import _parse
    from core.contracts import CoachingResult

    result = _parse(_GOOD_JSON)
    check("returns CoachingResult",           isinstance(result, CoachingResult))
    check("overall_assessment preserved",     "Strong session" in result.overall_assessment)
    check("strengths is tuple",               isinstance(result.strengths, tuple))
    check("improvements is tuple",            isinstance(result.improvements, tuple))
    check("key_insight preserved",            "basically" in result.key_insight)
    check("next_focus preserved",             "um" in result.next_focus)
    check("raw_json round-trips",             json.loads(result.raw_json) is not None)


    print("\n── T5  _parse — strips markdown fences ─────────────────")
    result2 = _parse(_FENCED_JSON)
    check("fenced JSON parsed correctly",
          result2.overall_assessment == result.overall_assessment)


    print("\n── T6  _parse — raises on bad input ────────────────────")
    for label, bad in [
        ("plain text (not JSON)",       _BAD_JSON),
        ("missing required keys",       _MISSING_KEY),
        ("empty overall_assessment",    _EMPTY_STR),
    ]:
        try:
            _parse(bad)
            check(f"raises on {label}", False, "no exception raised")
        except (ValueError, json.JSONDecodeError):
            check(f"raises on {label}", True)


    print("\n── T7  DummyCoach still works after LocalLLMCoach import ─")
    analytics, context = _make_context()
    dummy_result = DummyCoach().coach(_TRANSCRIPT, analytics, context)
    check("DummyCoach unaffected",  isinstance(dummy_result, CoachingResult))


    print("\n── T8  Real LLM inference ──────────────────────────────")
    print("  NOTE  Loading SmolLM2 and running inference.")
    print(f"        Model: {model_path.name}  ({model_path.stat().st_size // 1_000_000} MB)")
    print("        Expect 20–60 s on a 2016 Intel MacBook Pro.\n")

    analytics, context = _make_context()
    coach = LocalLLMCoach(model_path=str(model_path))

    t0     = time.monotonic()
    result = coach.coach(_TRANSCRIPT, analytics, context)
    elapsed = time.monotonic() - t0

    print(f"  INFO  Inference time: {elapsed:.1f} s")

    check("returns CoachingResult",           isinstance(result, CoachingResult))
    check("overall_assessment non-empty",     bool(result.overall_assessment.strip()))
    check("strengths non-empty",              len(result.strengths) > 0)
    check("improvements non-empty",           len(result.improvements) > 0)
    check("key_insight non-empty",            bool(result.key_insight.strip()))
    check("next_focus non-empty",             bool(result.next_focus.strip()))
    check("raw_json is valid JSON",           json.loads(result.raw_json) is not None)
    check("overall_assessment >= 20 chars",   len(result.overall_assessment) >= 20,
          result.overall_assessment)


    print("\n── T9  Full pipeline with LocalLLMCoach ─────────────────")
    print("  NOTE  Second inference call — expect similar timing.\n")

    from core.memory import MemoryStore
    from core.memory_engine import MemoryEngine
    from core.pipeline import SessionPipeline
    from core.transcriber import Transcriber
    from core.contracts import Segment, TranscriptionResult, RecordingResult
    from analytics._text import tokenize

    class _FakeTranscriber(Transcriber):
        def transcribe(self, recording):
            toks = tokenize(_TRANSCRIPT)
            return TranscriptionResult(
                text=_TRANSCRIPT,
                segments=(Segment(0.0, 20.0, _TRANSCRIPT, 0.83),),
                word_count=len(toks),
                speaking_rate_wpm=145.0,
            )

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "session.wav"
        wav.touch()
        recording = RecordingResult(
            wav_path=str(wav),
            duration_seconds=20.0,
            created_at=datetime.now(),
        )
        store  = MemoryStore(str(Path(tmp) / "sessions.db"))
        engine = MemoryEngine(store)
        pipe   = SessionPipeline(
            transcriber = _FakeTranscriber(),
            coach       = LocalLLMCoach(model_path=str(model_path)),
            store       = store,
            engine      = engine,
        )

        t0     = time.monotonic()
        sr     = pipe.run(recording)
        elapsed = time.monotonic() - t0

        print(f"  INFO  Full pipeline time: {elapsed:.1f} s")

        check("SessionResult returned",      sr.session_id == 1)
        check("LLM coaching in result",      bool(sr.coaching.overall_assessment.strip()))
        check("session saved to SQLite",     store.session_count() == 1)
        check("profile generated",           bool(sr.profile.notable_pattern))

        detail = store.session_detail(1)
        check("5 analytics rows in SQLite",  len(detail["analytics"]) == 5)

    print("\n✓  All tests passed. Phase 7 complete.\n")
    print(f"  SmolLM2 is wired. Inference: {elapsed:.0f} s end-to-end on your machine.")
    print("  Phase 8 (PyQt6 UI) is the final phase.\n")


if __name__ == "__main__":
    run()