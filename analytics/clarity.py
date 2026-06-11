"""
Stage 3 — Clarity dimension.
Measures structural coherence and repetition.
"""
from __future__ import annotations

from collections import Counter
from core.contracts import Dimension, DimensionResult, Insight, InsightType
from analytics._text import tokenize, content_words, ngrams, sentence_split
from analytics.constants import TOPIC_DRIFT_OVERLAP


def analyze(transcription, duration_seconds: float) -> DimensionResult:
    text     = transcription.text
    tokens   = tokenize(text)
    content  = content_words(tokens)
    sentences = sentence_split(text)

    # ── Repeated phrases (3- and 4-grams) ────────────────────────────────
    repeated_count = _repeated_phrase_count(tokens, content)

    # ── Sentence length ───────────────────────────────────────────────────
    lengths = [len(tokenize(s)) for s in sentences if tokenize(s)]
    avg_len = sum(lengths) / len(lengths) if lengths else 0.0

    # ── Topic drift ───────────────────────────────────────────────────────
    drift = _topic_drift(content)

    # ── Scoring ───────────────────────────────────────────────────────────
    repetition_penalty   = min(50.0, repeated_count * 12.0)
    drift_penalty        = 15.0 if drift else 0.0
    sentence_len_score   = _sentence_length_score(avg_len)

    coherence   = max(0.0, 100.0 - repetition_penalty - drift_penalty)
    final_score = round(coherence * 0.75 + sentence_len_score * 0.25, 1)

    # ── Insights ──────────────────────────────────────────────────────────
    insights: list[Insight] = []
    if drift:
        insights.append(Insight(InsightType.TOPIC_DRIFT, "lexical overlap < 10%"))

    return DimensionResult(
        dimension=Dimension.CLARITY,
        score=final_score,
        metrics={
            "repeated_phrase_count":  repeated_count,
            "avg_sentence_length":    round(avg_len, 1),
            "sentence_count":         len(sentences),
            "topic_drift":            drift,
            "repetition_penalty":     round(repetition_penalty, 1),
            "drift_penalty":          drift_penalty,
            "sentence_length_score":  round(sentence_len_score, 1),
        },
        feedback=_feedback(final_score, repeated_count, drift, avg_len),
        insights=tuple(insights),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _repeated_phrase_count(tokens: list[str], content: list[str]) -> int:
    """
    Count distinct 3- and 4-grams that appear ≥ 2 times
    and contain ≥ 2 content words.
    """
    content_set = set(content)
    count = 0
    for n in (3, 4):
        gram_counts = Counter(ngrams(tokens, n))
        for gram, freq in gram_counts.items():
            if freq >= 2 and sum(1 for w in gram if w in content_set) >= 2:
                count += 1
    return count


def _topic_drift(content: list[str]) -> bool:
    """
    Jaccard overlap between the first and last 20% of content words.
    Drift detected when overlap < TOPIC_DRIFT_OVERLAP.
    Returns False for content shorter than 10 words (insufficient signal).
    """
    if len(content) < 10:
        return False
    fifth  = max(1, len(content) // 5)
    first  = set(content[:fifth])
    last   = set(content[-fifth:])
    union  = first | last
    if not union:
        return False
    return (len(first & last) / len(union)) < TOPIC_DRIFT_OVERLAP


def _sentence_length_score(avg: float) -> float:
    if avg <= 0:
        return 50.0                              # insufficient data — neutral
    if 5 <= avg <= 25:
        return 100.0
    elif avg < 5:
        return max(0.0, 100.0 - (5 - avg) * 10.0)
    else:
        return max(0.0, 100.0 - (avg - 25) * 5.0)


def _feedback(score: float, repeated: int, drift: bool, avg_len: float) -> str:
    if score >= 80:
        return "Clear structure with good variety and no significant drift."
    parts: list[str] = []
    if repeated > 0:
        parts.append(f"You repeated {repeated} phrase(s). Vary your wording.")
    if drift:
        parts.append("Content drifted — your ending didn't connect back to your opening.")
    if avg_len > 25:
        parts.append("Sentences are long. Break them up for clarity.")
    elif 0 < avg_len < 5:
        parts.append("Sentences are very short. Try combining related ideas.")
    return " ".join(parts) if parts else "Clarity is moderate — focus on structure and variety."