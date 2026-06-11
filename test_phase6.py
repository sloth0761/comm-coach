"""
Standalone validation for Phase 6: analyzer, memory engine, pipeline.
Run from project root: python tests/test_phase6.py

Uses DummyTranscriber so Whisper is not required for pipeline tests.
Whisper was already validated in Phase 5.
"""
from __future__ import annotations

import sys
import tempfile
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
# Test doubles
# ---------------------------------------------------------------------------

from core.contracts import (
    AnalyticsBundle, CoachingResult, CommunicationProfile, Dimension,
    DimensionResult, Insight, InsightType, MemoryContext, RecordingResult,
    Segment, SessionResult, TranscriptionResult,
)
from core.transcriber import Transcriber
from core.analyzer import Coach


class DummyTranscriber(Transcriber):
    """Returns a realistic fake transcript — no Whisper needed."""
    TEXT = (
        "Um basically I think the pipeline architecture is solid. "
        "You know the memory engine makes this genuinely useful over time. "
        "Actually I believe we have built something with real staying power here. "
        "The deterministic analytics give us a stable foundation to build on. "
        "We should continue iterating and refining based on real user feedback."
    )

    def transcribe(self, recording: RecordingResult) -> TranscriptionResult:
        from analytics._text import tokenize
        tokens = tokenize(self.TEXT)
        return TranscriptionResult(
            text=self.TEXT,
            segments=(Segment(0.0, 15.0, self.TEXT, 0.84),),
            word_count=len(tokens),
            speaking_rate_wpm=148.0,
        )


class FailingCoach(Coach):
    """Always raises — tests the pipeline fallback path."""
    def coach(self, transcript, analytics, context) -> CoachingResult:
        raise RuntimeError("Simulated LLM failure")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_recording(tmp_dir: str) -> RecordingResult:
    """Create a zero-byte placeholder WAV path (pipeline never reads it directly)."""
    path = str(Path(tmp_dir) / "session.wav")
    Path(path).touch()
    return RecordingResult(
        wav_path=path,
        duration_seconds=30.0,
        created_at=datetime.now(),
    )


def _build_pipeline(tmp_dir: str, coach=None):
    """Wire a full pipeline with a temp SQLite db."""
    from core.memory import MemoryStore
    from core.memory_engine import MemoryEngine
    from core.pipeline import SessionPipeline
    from core.analyzer import DummyCoach

    store   = MemoryStore(str(Path(tmp_dir) / "sessions.db"))
    engine  = MemoryEngine(store)
    _coach  = coach or DummyCoach()
    pipe    = SessionPipeline(
        transcriber=DummyTranscriber(),
        coach=_coach,
        store=store,
        engine=engine,
    )
    return pipe, store, engine


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def run() -> None:

    print("\n── T1  CoachingError importable ────────────────────────")
    from core.analyzer import CoachingError, DummyCoach, LocalLLMCoach, make_coach
    check("CoachingError defined",    issubclass(CoachingError, Exception))
    check("DummyCoach is Coach",      issubclass(DummyCoach, Coach))
    check("LocalLLMCoach is Coach",   issubclass(LocalLLMCoach, Coach))


    print("\n── T2  DummyCoach deterministic output ─────────────────")
    from analytics import run_all

    tr = DummyTranscriber().transcribe(
        RecordingResult(wav_path="x.wav", duration_seconds=30.0, created_at=datetime.now())
    )
    analytics = run_all(tr, 30.0)
    context = MemoryContext(
        recent_sessions=(),
        recurring_patterns=(),
        trends={str(d): "stable" for d in Dimension},
        rendered="",
    )
    coaching = DummyCoach().coach(tr.text, analytics, context)

    check("returns CoachingResult",       isinstance(coaching, CoachingResult))
    check("overall_assessment non-empty", bool(coaching.overall_assessment))
    check("strengths non-empty",          len(coaching.strengths) > 0)
    check("improvements non-empty",       len(coaching.improvements) > 0)
    check("key_insight non-empty",        bool(coaching.key_insight))
    check("next_focus non-empty",         bool(coaching.next_focus))
    check("raw_json is valid JSON",
          __import__("json").loads(coaching.raw_json) is not None)


    print("\n── T3  make_coach factory ──────────────────────────────")
    cfg_no_model = SimpleNamespace(
        COACHING_BACKEND="local",
        LLAMA_MODEL_PATH="/nonexistent/model.gguf",
    )
    coach = make_coach(cfg_no_model)
    check("falls back to DummyCoach when GGUF missing", isinstance(coach, DummyCoach))

    cfg_bad = SimpleNamespace(COACHING_BACKEND="unknown", LLAMA_MODEL_PATH="x")
    try:
        make_coach(cfg_bad)
        check("ValueError on unknown backend", False)
    except ValueError:
        check("ValueError on unknown backend", True)

    cfg_cloud = SimpleNamespace(COACHING_BACKEND="claude", LLAMA_MODEL_PATH="x")
    try:
        make_coach(cfg_cloud)
        check("NotImplementedError on cloud backend", False)
    except NotImplementedError:
        check("NotImplementedError on cloud backend", True)


    print("\n── T4  MemoryEngine on empty store ─────────────────────")
    from core.memory import MemoryStore
    from core.memory_engine import MemoryEngine

    with tempfile.TemporaryDirectory() as tmp:
        store  = MemoryStore(str(Path(tmp) / "db.db"))
        engine = MemoryEngine(store)

        # assemble_context on empty store — should not crash
        context = engine.assemble_context(analytics, tr.text)
        check("MemoryContext returned",            isinstance(context, MemoryContext))
        check("recent_sessions empty",             len(context.recent_sessions) == 0)
        check("recurring_patterns empty",          len(context.recurring_patterns) == 0)
        check("trends has all 5 dimensions",       len(context.trends) == 5)
        check("all trends stable (no history)",    all(v == "stable" for v in context.trends.values()))
        check("rendered contains CURRENT SCORES",  "CURRENT SCORES" in context.rendered)
        check("rendered contains transcript",       tr.text[:50] in context.rendered)

        # generate_profile on empty store
        profile = engine.generate_profile()
        check("CommunicationProfile returned",    isinstance(profile, CommunicationProfile))
        check("no strengths yet",                  len(profile.strengths) == 0)
        check("no weaknesses yet",                 len(profile.recurring_weaknesses) == 0)
        check("notable_pattern is no-session msg", "No sessions" in profile.notable_pattern)


    print("\n── T5  Full pipeline run ───────────────────────────────")
    from core.pipeline import SessionPipeline, PipelineStage, PipelineError

    with tempfile.TemporaryDirectory() as tmp:
        stages_seen: list[PipelineStage] = []
        store  = MemoryStore(str(Path(tmp) / "db.db"))
        engine = MemoryEngine(store)
        pipe   = SessionPipeline(
            transcriber = DummyTranscriber(),
            coach       = DummyCoach(),
            store       = store,
            engine      = engine,
            on_stage    = stages_seen.append,
        )

        recording = _make_recording(tmp)
        result    = pipe.run(recording)

        check("returns SessionResult",    isinstance(result, SessionResult))
        check("session_id == 1",          result.session_id == 1)
        check("transcription populated",  result.transcription.word_count > 0)
        check("analytics populated",      result.analytics.overall_score > 0)
        check("coaching populated",       bool(result.coaching.overall_assessment))
        check("profile populated",        isinstance(result.profile, CommunicationProfile))


    print("\n── T6  Stage events fire in order ──────────────────────")
    expected = [
        PipelineStage.TRANSCRIBING,
        PipelineStage.ANALYZING,
        PipelineStage.ASSEMBLING_MEMORY,
        PipelineStage.COACHING,
        PipelineStage.SAVING,
        PipelineStage.DONE,
    ]
    check("all 6 stages fired",       stages_seen == expected, stages_seen)


    print("\n── T7  SQLite has the session ──────────────────────────")
    with tempfile.TemporaryDirectory() as tmp:
        pipe, store, engine = _build_pipeline(tmp)
        pipe.run(_make_recording(tmp))

        check("session_count == 1",        store.session_count() == 1)
        detail = store.session_detail(1)
        check("session_detail returned",   bool(detail))
        check("5 analytics rows",          len(detail["analytics"]) == 5)
        check("insights persisted",        len(detail["insights"]) > 0)
        check("overall_score persisted",   detail["overall_score"] > 0)


    print("\n── T8  Communication Profile after sessions ─────────────")
    with tempfile.TemporaryDirectory() as tmp:
        pipe, store, engine = _build_pipeline(tmp)

        # Run 3 sessions so profile has enough data
        for _ in range(3):
            pipe.run(_make_recording(tmp))

        profile = engine.generate_profile()
        check("session_count == 3",           store.session_count() == 3)
        check("profile notable_pattern set",  "sessions" in profile.notable_pattern)
        check("trends dict has 5 keys",       len(profile.trends) == 5)

        # If any filler words appeared 3 times in 3 sessions they're persistent
        pf = store.persistent_fillers()
        check("persistent_fillers query ok",  isinstance(pf, list))


    print("\n── T9  Short transcript raises PipelineError ────────────")

    class ShortTranscriber(Transcriber):
        def transcribe(self, recording):
            return TranscriptionResult(
                text="too short",
                segments=(),
                word_count=2,
                speaking_rate_wpm=0.0,
            )

    with tempfile.TemporaryDirectory() as tmp:
        store  = MemoryStore(str(Path(tmp) / "db.db"))
        engine = MemoryEngine(store)
        pipe   = SessionPipeline(
            transcriber=ShortTranscriber(),
            coach=DummyCoach(),
            store=store,
            engine=engine,
        )
        try:
            pipe.run(_make_recording(tmp))
            check("PipelineError raised on short transcript", False)
        except PipelineError:
            check("PipelineError raised on short transcript", True)
        check("session NOT saved on short transcript", store.session_count() == 0)


    print("\n── T10  Coaching failure → fallback, session still saved ─")
    with tempfile.TemporaryDirectory() as tmp:
        pipe, store, engine = _build_pipeline(tmp, coach=FailingCoach())
        result = pipe.run(_make_recording(tmp))

        check("SessionResult returned despite coaching failure", isinstance(result, SessionResult))
        check("session saved despite coaching failure",          store.session_count() == 1)
        check("fallback coaching populated",                     bool(result.coaching.overall_assessment))


    print("\n── T11  MemoryContext rendered block content ────────────")
    with tempfile.TemporaryDirectory() as tmp:
        pipe, store, engine = _build_pipeline(tmp)
        pipe.run(_make_recording(tmp))   # seed one session into history

        tr2 = DummyTranscriber().transcribe(_make_recording(tmp))
        analytics2 = run_all(tr2, 30.0)
        ctx = engine.assemble_context(analytics2, tr2.text)

        check("HISTORY section present",       "HISTORY" in ctx.rendered)
        check("CURRENT SCORES present",        "CURRENT SCORES" in ctx.rendered)
        check("recent_sessions has 1 entry",   len(ctx.recent_sessions) == 1)
        check("trends has 5 dimensions",       len(ctx.trends) == 5)


    print("\n✓  All tests passed. Phase 6 complete.\n")


if __name__ == "__main__":
    run()