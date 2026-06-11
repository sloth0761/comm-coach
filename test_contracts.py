"""
Standalone validation for core/contracts.py.
Run from project root: python tests/test_contracts.py
"""
import sys
from dataclasses import FrozenInstanceError
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.contracts import (
    AnalyticsBundle,
    CoachingResult,
    CommunicationProfile,
    Dimension,
    DimensionResult,
    Insight,
    InsightType,
    MemoryContext,
    RecordingResult,
    Segment,
    SessionResult,
    TranscriptionResult,
)


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        sys.exit(1)


def run() -> None:

    print("\n── T1  Enums ───────────────────────────────────────────")
    check(
        "Dimension members",
        list(Dimension) == [
            "fluency", "clarity", "expression",
            "speech_signal_clarity", "conciseness",
        ],
    )
    check("InsightType count",    len(InsightType) == 7)
    check("StrEnum str coercion", str(Dimension.FLUENCY) == "fluency")
    check("StrEnum equality",     Dimension.FLUENCY == "fluency")
    check(
        "InsightType coercion",
        str(InsightType.OVERUSES_FILLER) == "overuses_filler",
    )

    print("\n── T2  Segment confidence clamping ─────────────────────")
    s_low  = Segment(0.0, 1.0, "test", confidence=-0.5)
    s_high = Segment(0.0, 1.0, "test", confidence=1.8)
    s_ok   = Segment(0.0, 1.0, "test", confidence=0.75)
    check("negative clamped to 0.0",  s_low.confidence  == 0.0,  str(s_low.confidence))
    check("overflow clamped to 1.0",  s_high.confidence == 1.0,  str(s_high.confidence))
    check("valid value preserved",    s_ok.confidence   == 0.75, str(s_ok.confidence))

    print("\n── T3  Frozen enforcement ──────────────────────────────")
    rec = RecordingResult(
        wav_path="x.wav",
        duration_seconds=60.0,
        created_at=datetime.now(),
    )
    try:
        rec.wav_path = "y.wav"   # type: ignore[misc]
        check("FrozenInstanceError raised", False, "no exception raised")
    except FrozenInstanceError:
        check("FrozenInstanceError raised", True)

    print("\n── T4  RecordingResult default sample_rate ─────────────")
    check("default sample_rate == 16_000", rec.sample_rate == 16_000)

    print("\n── T5  DimensionResult filler_events default ───────────")
    bare = DimensionResult(
        dimension=Dimension.CLARITY,
        score=70.0,
        metrics={},
        feedback="ok",
        insights=(),
    )
    check("filler_events defaults to {}", bare.filler_events == {})

    print("\n── T6  Full SessionResult construction (inside-out) ────")

    # Stage 1
    recording = RecordingResult(
        wav_path="data/recordings/session.wav",
        duration_seconds=120.0,
        created_at=datetime.now(),
    )

    # Stage 2
    seg = Segment(start=0.0, end=3.5, text="Um hello basically", confidence=0.82)
    transcription = TranscriptionResult(
        text="Um hello basically",
        segments=(seg,),
        word_count=3,
        speaking_rate_wpm=90.0,
    )

    # Stage 3
    insight = Insight(insight_type=InsightType.OVERUSES_FILLER, value="um")
    fluency = DimensionResult(
        dimension=Dimension.FLUENCY,
        score=58.0,
        metrics={"filler_count": 4, "wpm": 90.0},
        feedback="Reduce filler words.",
        insights=(insight,),
        filler_events={"um": 4},
    )
    other_dims = tuple(
        DimensionResult(
            dimension=d,
            score=70.0,
            metrics={},
            feedback=f"{d} ok.",
            insights=(),
        )
        for d in (
            Dimension.CLARITY,
            Dimension.EXPRESSION,
            Dimension.SPEECH_SIGNAL_CLARITY,
            Dimension.CONCISENESS,
        )
    )
    bundle = AnalyticsBundle(
        dimensions=(fluency,) + other_dims,
        overall_score=67.0,
    )

    # Memory Engine
    context = MemoryContext(
        recent_sessions=({"id": 1, "overall_score": 65.0},),
        recurring_patterns=('overuses_filler "um" (5 of 6 sessions)',),
        trends={"fluency": "improving", "conciseness": "declining"},
        rendered="HISTORY\n...",
    )

    # Stage 4
    coaching = CoachingResult(
        overall_assessment="Solid session with clear room to improve.",
        strengths=("Good sentence length",),
        improvements=("Cut filler words",),
        key_insight="'Um' appears 4x more than your target.",
        next_focus="Record one minute with zero fillers.",
        raw_json='{"overall_assessment": "Solid."}',
    )

    # Profile
    profile = CommunicationProfile(
        strengths=("Strong vocabulary",),
        recurring_weaknesses=('overuses_filler "um"',),
        trends={"fluency": "improving"},
        persistent_fillers=({"word": "um", "sessions_with": 5, "total": 22},),
        notable_pattern='"um" appears in 5 of 6 sessions.',
    )

    # Full nesting
    result = SessionResult(
        session_id=1,
        recording=recording,
        transcription=transcription,
        analytics=bundle,
        coaching=coaching,
        profile=profile,
    )

    check("5 dimensions in bundle",        len(result.analytics.dimensions) == 5)
    check("deep insight value",            result.analytics.dimensions[0].insights[0].value == "um")
    check("deep filler_events",            result.analytics.dimensions[0].filler_events["um"] == 4)
    check("enum survives nesting",         result.analytics.dimensions[0].dimension == Dimension.FLUENCY)
    check("MemoryContext trends",          context.trends["fluency"] == "improving")
    check("profile persistent_fillers",    result.profile.persistent_fillers[0]["word"] == "um")
    check("segment confidence preserved",  result.transcription.segments[0].confidence == 0.82)

    print("\n✓  All tests passed. Phase 3 complete.\n")


if __name__ == "__main__":
    run()