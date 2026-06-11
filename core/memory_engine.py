"""
Memory Engine — the component that makes Comm Coach a growth system rather than
a one-shot analyser.

v1:  pure structured retrieval from SQLite (this file).
v1.5: assemble_context gains a semantic step that reads session_embeddings.
      The MemoryContext contract and everything that consumes it stay unchanged.
"""
from __future__ import annotations

import logging
from core.contracts import (
    AnalyticsBundle, CommunicationProfile, Dimension, MemoryContext,
)
from core.memory import MemoryStore

logger = logging.getLogger(__name__)

_TRANSCRIPT_MAX_CHARS = 2_500
_TREND_WINDOW         = 10      # sessions used per trend calculation
_TREND_THRESHOLD      = 5.0     # score points to count as improving/declining
_STRENGTH_THRESHOLD   = 75.0    # average score to count as a strength
_WEAKNESS_MIN_SESSIONS = 3      # sessions to count as a recurring weakness


class MemoryEngine:

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    # ------------------------------------------------------------------
    # Stage 4 context assembly
    # ------------------------------------------------------------------

    def assemble_context(
        self,
        current: AnalyticsBundle,
        transcript: str,
    ) -> MemoryContext:
        """
        Build the structured context block that Stage 4 (coaching) receives.

        v1 sources:
          • Last 5 sessions with per-dimension scores (structured query)
          • Top 3 recurring insight types with session counts
          • Per-dimension trend direction over last 10 sessions

        v1.5 addition: semantically similar sessions via session_embeddings.
        The contract (MemoryContext) and the LLM prompt format don't change.
        """
        recent   = self._store.recent_sessions(limit=5)
        freqs    = self._store.insight_frequencies()

        # Pre-render top 3 patterns for the prompt
        recurring: tuple[str, ...] = tuple(
            f"{insight_type} (in {n} sessions)"
            for insight_type, n, _ in freqs[:3]
        )

        # Trend per dimension
        trends: dict[str, str] = {
            str(dim): _compute_trend(
                self._store.dimension_series(str(dim), limit=_TREND_WINDOW)
            )
            for dim in Dimension
        }

        rendered = _render_prompt_block(transcript, current, recent, recurring, trends)

        return MemoryContext(
            recent_sessions=tuple(recent),
            recurring_patterns=recurring,
            trends=trends,
            rendered=rendered,
        )

    # ------------------------------------------------------------------
    # Communication Profile
    # ------------------------------------------------------------------

    def generate_profile(self) -> CommunicationProfile:
        """
        Derive the Communication Profile from all accumulated sessions.
        Pure SQLite aggregation — no LLM required in v1.
        Called automatically after each new session is saved.
        """
        n = self._store.session_count()

        if n == 0:
            return CommunicationProfile(
                strengths=(),
                recurring_weaknesses=(),
                trends={str(d): "stable" for d in Dimension},
                persistent_fillers=(),
                notable_pattern="No sessions yet.",
            )

        # Strengths — dimensions averaging above threshold across all sessions
        strengths: list[str] = []
        trends: dict[str, str] = {}
        for dim in Dimension:
            # limit=10_000 is a practical ceiling; optimise in v1.5 if needed
            series = self._store.dimension_series(str(dim), limit=10_000)
            if series:
                avg = sum(series) / len(series)
                if avg > _STRENGTH_THRESHOLD:
                    strengths.append(f"{dim} (avg {avg:.0f})")
            trends[str(dim)] = _compute_trend(
                series[-_TREND_WINDOW:] if series else []
            )

        # Recurring weaknesses — insight types appearing in 3+ sessions
        freqs = self._store.insight_frequencies()
        weaknesses: tuple[str, ...] = tuple(
            f"{insight_type} ({n_sessions} sessions)"
            for insight_type, n_sessions, _ in freqs
            if n_sessions >= _WEAKNESS_MIN_SESSIONS
        )

        # Persistent fillers — present in > 50% of sessions
        persistent: tuple[dict, ...] = tuple(
            dict(row) for row in self._store.persistent_fillers()
        )

        # Notable pattern — highest-frequency insight with a plain-English summary
        notable = "No recurring patterns detected yet."
        if freqs:
            top_type, top_sessions, top_total = freqs[0]
            avg_per = top_total / n if n else 0
            notable = (
                f'"{top_type}" is your most consistent pattern — '
                f"appearing in {top_sessions} of {n} sessions "
                f"({avg_per:.1f} occurrences per session on average)."
            )

        return CommunicationProfile(
            strengths=tuple(strengths),
            recurring_weaknesses=weaknesses,
            trends=trends,
            persistent_fillers=persistent,
            notable_pattern=notable,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_trend(series: list[float]) -> str:
    """
    Compare the mean of the older half vs the recent half of a score series.
    Series is oldest-first (as returned by MemoryStore.dimension_series).
    Requires at least 4 data points to return a non-stable result.
    """
    if len(series) < 4:
        return "stable"
    mid     = len(series) // 2
    earlier = sum(series[:mid]) / mid
    recent  = sum(series[mid:]) / (len(series) - mid)
    diff    = recent - earlier
    if diff >= _TREND_THRESHOLD:
        return "improving"
    if diff <= -_TREND_THRESHOLD:
        return "declining"
    return "stable"


def _render_prompt_block(
    transcript: str,
    current: AnalyticsBundle,
    recent: list[dict],
    recurring: tuple[str, ...],
    trends: dict[str, str],
) -> str:
    """
    Render the structured context string passed to the LLM (PRD §9).
    Transcript is hard-capped at _TRANSCRIPT_MAX_CHARS characters.
    """
    score = {d.dimension: d.score for d in current.dimensions}
    lines: list[str] = []

    lines.append("CURRENT TRANSCRIPT")
    lines.append(transcript[:_TRANSCRIPT_MAX_CHARS])
    lines.append("")

    lines.append("CURRENT SCORES")
    lines.append(
        f"Fluency: {score.get('fluency', 0):.0f} | "
        f"Clarity: {score.get('clarity', 0):.0f} | "
        f"Expression: {score.get('expression', 0):.0f} | "
        f"Speech Signal Clarity: {score.get('speech_signal_clarity', 0):.0f} | "
        f"Conciseness: {score.get('conciseness', 0):.0f}"
    )
    lines.append("")

    if recent:
        lines.append(f"HISTORY (last {len(recent)} sessions)")
        for s in recent:
            lines.append(
                f"{s.get('created_at', 'unknown')}: "
                f"{s.get('word_count', 0)} words, "
                f"{s.get('speaking_rate_wpm', 0):.0f} WPM | "
                f"Fluency {s.get('fluency') or 0:.0f}, "
                f"Clarity {s.get('clarity') or 0:.0f}, "
                f"Expression {s.get('expression') or 0:.0f}, "
                f"SSC {s.get('ssc') or 0:.0f}, "
                f"Conciseness {s.get('conciseness') or 0:.0f}"
            )
        lines.append("")

    non_stable = [(d, v) for d, v in trends.items() if v != "stable"]
    if recurring or non_stable:
        lines.append("RECURRING PATTERNS")
        for pattern in recurring:
            lines.append(f"- {pattern}")
        for dim, direction in non_stable:
            lines.append(f"- {dim} trend: {direction}")

    return "\n".join(lines)