"""
Stage 3 — Fluency dimension.
Measures verbal habits that interrupt communication flow.
"""
from __future__ import annotations

import re
from core.contracts import Dimension, DimensionResult, Insight, InsightType
from analytics._text import tokenize
from analytics.constants import OVERUSES_FILLER_MIN, TALKS_TOO_FAST_WPM

# Multi-word fillers are checked before single-word ones to prevent double-counting.
_MULTI_WORD_FILLERS: list[str] = ["you know", "kind of", "sort of"]

_SINGLE_WORD_FILLERS: frozenset[str] = frozenset({
    "um", "uh", "ah", "er", "like", "basically", "literally",
    "actually", "right", "so", "well", "okay", "hmm",
})

_MULTI_PATTERNS: dict[str, re.Pattern] = {
    phrase: re.compile(
        r"\b" + r"\s+".join(re.escape(w) for w in phrase.split()) + r"\b",
        re.IGNORECASE,
    )
    for phrase in _MULTI_WORD_FILLERS
}

_PAUSE_THRESHOLD = 0.5   # seconds between segments


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def analyze(transcription, duration_seconds: float) -> DimensionResult:
    text     = transcription.text
    segments = transcription.segments
    wpm      = transcription.speaking_rate_wpm
    tokens   = tokenize(text)
    total_words = len(tokens)

    # ── Filler detection ──────────────────────────────────────────────────
    filler_events: dict[str, int] = {}
    working = text.lower()

    # Check multi-word fillers first; remove matches so they aren't counted again
    for phrase, pattern in _MULTI_PATTERNS.items():
        matches = pattern.findall(working)
        if matches:
            filler_events[phrase] = len(matches)
            working = pattern.sub(" ", working)

    # Single-word fillers on whatever text remains
    for token in tokenize(working):
        if token in _SINGLE_WORD_FILLERS:
            filler_events[token] = filler_events.get(token, 0) + 1

    total_fillers = sum(filler_events.values())
    filler_rate   = (total_fillers / total_words * 100) if total_words else 0.0

    # ── Pauses ────────────────────────────────────────────────────────────
    pause_count = sum(
        1 for i in range(1, len(segments))
        if segments[i].start - segments[i - 1].end > _PAUSE_THRESHOLD
    )

    # ── Scoring ───────────────────────────────────────────────────────────
    filler_score = max(0.0, 100.0 - filler_rate * 10.0)
    wpm_score    = _wpm_score(wpm)
    final_score  = round(filler_score * 0.65 + wpm_score * 0.35, 1)

    # ── Insights ──────────────────────────────────────────────────────────
    insights: list[Insight] = []
    for word, count in filler_events.items():
        if count >= OVERUSES_FILLER_MIN:
            insights.append(Insight(InsightType.OVERUSES_FILLER, word))
    if wpm >= TALKS_TOO_FAST_WPM:
        insights.append(Insight(InsightType.TALKS_TOO_FAST, f"{wpm:.0f} WPM"))

    return DimensionResult(
        dimension=Dimension.FLUENCY,
        score=final_score,
        metrics={
            "filler_count":         total_fillers,
            "filler_rate_per_100":  round(filler_rate, 2),
            "filler_events":        filler_events,
            "wpm":                  round(wpm, 1),
            "pause_count":          pause_count,
            "filler_score":         round(filler_score, 1),
            "wpm_score":            round(wpm_score, 1),
        },
        feedback=_feedback(filler_score, wpm, filler_events),
        insights=tuple(insights),
        filler_events=filler_events,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _wpm_score(wpm: float) -> float:
    if 120 <= wpm <= 160:
        return 100.0
    elif 100 <= wpm < 120:
        return 50.0 + (wpm - 100) * 2.5     # 50 at 100 WPM, 100 at 120 WPM
    elif 160 < wpm <= 180:
        return 50.0 + (180 - wpm) * 2.5     # 100 at 160 WPM, 50 at 180 WPM
    return 0.0


def _feedback(filler_score: float, wpm: float, filler_events: dict) -> str:
    if filler_score >= 80 and 100 <= wpm <= 180:
        return "Strong fluency — natural pace with minimal filler words."
    parts: list[str] = []
    if filler_score < 80 and filler_events:
        top = max(filler_events, key=lambda w: filler_events[w])
        parts.append(f'Watch filler words — "{top}" appeared {filler_events[top]} times.')
    if wpm < 100:
        parts.append("Pace is slow. Aim for 120–160 words per minute.")
    elif wpm > 180:
        parts.append("Pace is fast. Aim for 120–160 words per minute.")
    elif wpm > 160:
        parts.append("Pace is slightly fast. Try slowing down a little.")
    return " ".join(parts) if parts else "Fluency is reasonable but has room to improve."