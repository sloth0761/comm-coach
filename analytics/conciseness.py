"""
Stage 3 — Conciseness dimension.
Measures whether ideas are communicated efficiently.
Particularly valuable for interview prep, presentations, and leadership communication.
"""
from __future__ import annotations

import re
from core.contracts import Dimension, DimensionResult, Insight, InsightType
from analytics._text import tokenize, content_words, sentence_split, content_word_density
from analytics.constants import VERBOSE_PHRASES_MIN, REPEATED_IDEAS_MIN

_VERBOSE_PHRASES: list[str] = [
    "in order to",
    "due to the fact that",
    "at this point in time",
    "what i'm trying to say is",
    "what im trying to say is",
    "the thing is that",
    "i just wanted to",
    "basically what happened was",
]

_VERBOSE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
    for phrase in _VERBOSE_PHRASES
]


def analyze(transcription, duration_seconds: float) -> DimensionResult:
    text    = transcription.text
    tokens  = tokenize(text)
    content = content_words(tokens)

    # ── Verbose phrase count ──────────────────────────────────────────────
    verbose_count = sum(len(p.findall(text)) for p in _VERBOSE_PATTERNS)

    # ── Repeated ideas ────────────────────────────────────────────────────
    repeated_ideas = _repeated_idea_count(sentence_split(text))

    # ── Content word density ──────────────────────────────────────────────
    density = content_word_density(tokens, content)

    # ── Scoring ───────────────────────────────────────────────────────────
    verbose_penalty = min(30.0, verbose_count  * 5.0)
    idea_penalty    = min(30.0, repeated_ideas * 10.0)
    # Density 0.5 → 100; scale linearly, cap at 100
    density_score   = min(100.0, density * 200.0)

    raw_score   = max(0.0, 100.0 - verbose_penalty - idea_penalty)
    final_score = round(raw_score * 0.6 + density_score * 0.4, 1)

    # ── Insights ──────────────────────────────────────────────────────────
    insights: list[Insight] = []
    if verbose_count >= VERBOSE_PHRASES_MIN:
        insights.append(Insight(InsightType.VERBOSE_PHRASES, f"{verbose_count} found"))
    if repeated_ideas >= REPEATED_IDEAS_MIN:
        insights.append(Insight(InsightType.REPEATED_IDEAS, f"{repeated_ideas} pairs"))

    return DimensionResult(
        dimension=Dimension.CONCISENESS,
        score=final_score,
        metrics={
            "verbose_phrase_count": verbose_count,
            "repeated_idea_count":  repeated_ideas,
            "content_word_density": round(density, 3),
            "verbose_penalty":      round(verbose_penalty, 1),
            "idea_penalty":         round(idea_penalty, 1),
            "density_score":        round(density_score, 1),
        },
        feedback=_feedback(final_score, verbose_count, repeated_ideas, density),
        insights=tuple(insights),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _repeated_idea_count(sentences: list[str]) -> int:
    """
    Count pairs of sentences whose content words share > 60% Jaccard similarity.
    Each pair is counted once. Short or empty sentences are skipped.
    """
    if len(sentences) < 2:
        return 0

    sets: list[set[str]] = [
        set(content_words(tokenize(s))) for s in sentences
    ]

    count = 0
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            a, b = sets[i], sets[j]
            if not a or not b:
                continue
            union = a | b
            if union and len(a & b) / len(union) > 0.6:
                count += 1
    return count


def _feedback(score: float, verbose: int, ideas: int, density: float) -> str:
    if score >= 80:
        return "Concise and efficient — ideas are communicated directly."
    parts: list[str] = []
    if verbose >= VERBOSE_PHRASES_MIN:
        parts.append(
            f"Found {verbose} verbose phrase(s). "
            "Cut constructions like 'in order to' and 'due to the fact that'."
        )
    if ideas >= REPEATED_IDEAS_MIN:
        parts.append(f"You restated the same idea {ideas} time(s). Say it once, say it well.")
    if density < 0.35:
        parts.append("Low content density — too many function words. Be more direct.")
    return " ".join(parts) if parts else "Conciseness is moderate. Look for places to say more with less."