"""
Analytics aggregator.
Runs all five dimension modules in pipeline order and computes the weighted overall score.
"""
from __future__ import annotations

from core.contracts import AnalyticsBundle, Dimension
from analytics import fluency, clarity, expression, speech_signal_clarity, conciseness

# Weights as defined in PRD §7. Must sum to 1.0.
WEIGHTS: dict[Dimension, float] = {
    Dimension.FLUENCY:               0.25,
    Dimension.CLARITY:               0.20,
    Dimension.EXPRESSION:            0.20,
    Dimension.SPEECH_SIGNAL_CLARITY: 0.20,
    Dimension.CONCISENESS:           0.15,
}

_MODULES = {
    Dimension.FLUENCY:               fluency,
    Dimension.CLARITY:               clarity,
    Dimension.EXPRESSION:            expression,
    Dimension.SPEECH_SIGNAL_CLARITY: speech_signal_clarity,
    Dimension.CONCISENESS:           conciseness,
}


def run_all(transcription, duration_seconds: float) -> AnalyticsBundle:
    """
    Run all five dimension modules and return an AnalyticsBundle.
    Execution order matches WEIGHTS (dict insertion order, Python 3.7+).
    No model required — pure Python throughout.
    """
    results = tuple(
        module.analyze(transcription, duration_seconds)
        for module in _MODULES.values()
    )
    score_map   = {r.dimension: r.score for r in results}
    overall     = round(
        sum(score_map[dim] * weight for dim, weight in WEIGHTS.items()), 1
    )
    return AnalyticsBundle(dimensions=results, overall_score=overall)