"""
Stage 3 — Speech Signal Clarity dimension.
Measures how consistently Whisper parsed the audio signal.
Proxy for enunciation quality — not a direct phoneme measurement.
Will be upgraded to true articulation analysis in v2.
"""
from __future__ import annotations

from core.contracts import Dimension, DimensionResult, Insight, InsightType
from analytics.constants import LOW_SIGNAL_CONF, LOW_SIGNAL_SEGMENTS_MIN


def analyze(transcription, duration_seconds: float) -> DimensionResult:
    segments = transcription.segments

    if not segments:
        return DimensionResult(
            dimension=Dimension.SPEECH_SIGNAL_CLARITY,
            score=0.0,
            metrics={"segment_count": 0},
            feedback="No segments found — cannot evaluate signal clarity.",
            insights=(),
        )

    # ── Metrics ───────────────────────────────────────────────────────────
    confidences      = [seg.confidence for seg in segments]
    avg_confidence   = sum(confidences) / len(confidences)
    low_conf_count   = sum(1 for c in confidences if c < LOW_SIGNAL_CONF)

    # ── Scoring ───────────────────────────────────────────────────────────
    # Confidence is already normalised to [0, 1] by Segment.__post_init__.
    final_score = round(avg_confidence * 100.0, 1)

    # ── Insights ──────────────────────────────────────────────────────────
    insights: list[Insight] = []
    if low_conf_count >= LOW_SIGNAL_SEGMENTS_MIN:
        insights.append(
            Insight(InsightType.LOW_SIGNAL_CLARITY, f"{low_conf_count} low-confidence segments")
        )

    return DimensionResult(
        dimension=Dimension.SPEECH_SIGNAL_CLARITY,
        score=final_score,
        metrics={
            "avg_confidence":          round(avg_confidence, 3),
            "low_confidence_segments": low_conf_count,
            "segment_count":           len(segments),
        },
        feedback=_feedback(final_score, low_conf_count, len(segments)),
        insights=tuple(insights),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _feedback(score: float, low_conf: int, total: int) -> str:
    if score >= 80:
        return "Clear audio signal — speech was consistently well-parsed."
    if score >= 60:
        pct = f"{low_conf / total:.0%}" if total else "0%"
        return (
            f"{low_conf} of {total} segments were difficult to parse ({pct}). "
            "Check your microphone or try speaking more deliberately."
        )
    return (
        "Signal clarity is low. Poor enunciation or microphone issues may be affecting results. "
        "Speak towards the microphone and articulate each word clearly."
    )