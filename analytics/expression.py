"""
Stage 3 — Expression dimension.
Measures vocabulary richness and precision.
"""
from __future__ import annotations

from core.contracts import Dimension, DimensionResult, Insight, InsightType
from analytics._text import tokenize, content_words, corrected_ttr
from analytics.constants import STRONG_VOCAB_TTR


def analyze(transcription, duration_seconds: float) -> DimensionResult:
    text    = transcription.text
    tokens  = tokenize(text)
    content = content_words(tokens)

    if not content:
        return DimensionResult(
            dimension=Dimension.EXPRESSION,
            score=0.0,
            metrics={"error": "no content words detected"},
            feedback="Transcript too short to evaluate expression.",
            insights=(),
        )

    # ── Metrics ───────────────────────────────────────────────────────────
    ttr           = corrected_ttr(tokens, content)
    unique_count  = len(set(content))
    complex_words = [w for w in content if len(w) > 7]
    complex_ratio = len(complex_words) / len(content)
    avg_word_len  = sum(len(w) for w in content) / len(content)

    # ── Scoring ───────────────────────────────────────────────────────────
    diversity_score   = min(100.0, ttr * 100.0)
    complexity_score  = min(100.0, complex_ratio * 250.0)
    final_score       = round(diversity_score * 0.6 + complexity_score * 0.4, 1)

    # ── Insights ──────────────────────────────────────────────────────────
    insights: list[Insight] = []
    if ttr >= STRONG_VOCAB_TTR:
        insights.append(Insight(InsightType.STRONG_VOCABULARY, f"diversity={ttr:.2f}"))

    return DimensionResult(
        dimension=Dimension.EXPRESSION,
        score=final_score,
        metrics={
            "corrected_ttr":          round(ttr, 3),
            "unique_content_words":   unique_count,
            "total_content_words":    len(content),
            "complex_word_ratio":     round(complex_ratio, 3),
            "avg_content_word_length": round(avg_word_len, 2),
            "diversity_score":        round(diversity_score, 1),
            "complexity_score":       round(complexity_score, 1),
        },
        feedback=_feedback(final_score, ttr, complex_ratio),
        insights=tuple(insights),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _feedback(score: float, ttr: float, complex_ratio: float) -> str:
    if score >= 80:
        return "Rich, varied vocabulary with good word precision."
    parts: list[str] = []
    if ttr < 0.5:
        parts.append("You're reusing many of the same words. Try varying your vocabulary.")
    elif ttr < STRONG_VOCAB_TTR:
        parts.append("Vocabulary is reasonable — push for more variety.")
    if complex_ratio < 0.10:
        parts.append("Most words are simple. Introducing more precise terms would add depth.")
    return " ".join(parts) if parts else "Expression is average — vary both word choice and complexity."