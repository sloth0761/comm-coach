"""
Standalone validation for the analytics engine (Phase 4).
Run from project root: python tests/test_analytics.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.contracts import Dimension, InsightType
from analytics._text import (
    tokenize, content_words, corrected_ttr, ngrams, sentence_split,
    content_word_density,
)
import analytics.fluency          as fluency_mod
import analytics.clarity          as clarity_mod
import analytics.expression       as expression_mod
import analytics.speech_signal_clarity as ssc_mod
import analytics.conciseness      as conciseness_mod
from analytics import run_all, WEIGHTS


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Fake TranscriptionResult helpers (contracts not wired to analyser yet)
# ---------------------------------------------------------------------------

def _seg(start: float, end: float, confidence: float) -> SimpleNamespace:
    return SimpleNamespace(start=start, end=end, confidence=confidence)


def _tr(text: str, wpm: float = 140.0, segments: list | None = None) -> SimpleNamespace:
    if segments is None:
        segments = [_seg(0.0, 2.0, 0.85)]
    return SimpleNamespace(
        text=text,
        segments=segments,
        word_count=len(tokenize(text)),
        speaking_rate_wpm=wpm,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def run() -> None:

    print("\n── T1  _text utilities ─────────────────────────────────")

    tokens = tokenize("Um, hello — I think this is GREAT!")
    check("tokenize lowercases",    all(t == t.lower() for t in tokens))
    check("tokenize strips punct",  not any(c in ".,—!'" for t in tokens for c in t))
    check("tokenize splits words",  "um" in tokens and "hello" in tokens)

    content = content_words(tokenize("The quick brown fox jumps over the lazy dog"))
    check("stopwords removed",      "the" not in content and "over" not in content)
    check("nouns kept",             "fox" in content and "dog" in content)

    grams = ngrams(["a", "b", "c", "d"], 2)
    check("ngrams count",           len(grams) == 3)
    check("ngrams values",          grams == [("a","b"),("b","c"),("c","d")])

    sents = sentence_split("First sentence. Second one! Third?")
    check("sentence_split count",   len(sents) == 3)

    # corrected_ttr: content = ["b","c","b"] → unique={"b","c"}, total=3 → 2/3
    ttr = corrected_ttr(["a","b","c","a"], ["b","c","b"])
    check("corrected_ttr",          abs(ttr - 2/3) < 0.01, ttr)

    density = content_word_density(["the","cat","sat"], ["cat","sat"])
    check("content_word_density",   abs(density - 2/3) < 0.01, density)


    print("\n── T2  Fluency ─────────────────────────────────────────")

    # Heavy filler usage
    filler_text = ("um " * 20 + "hello world " * 5).strip()
    r = fluency_mod.analyze(_tr(filler_text, wpm=140), 60.0)
    check("dimension == FLUENCY",         r.dimension == Dimension.FLUENCY)
    check("score < 50 (high filler rate)", r.score < 50.0,  r.score)
    check("um in filler_events",          "um" in r.filler_events)
    check("overuses_filler insight",
          any(i.insight_type == InsightType.OVERUSES_FILLER for i in r.insights))

    # Clean speech at good pace
    clean = "The architecture separates concerns cleanly. Each module has one responsibility."
    r_clean = fluency_mod.analyze(_tr(clean, wpm=140), 30.0)
    check("clean fluency > 80",           r_clean.score > 80.0,  r_clean.score)
    check("no insights on clean speech",  len(r_clean.insights) == 0)

    # Too fast
    r_fast = fluency_mod.analyze(_tr(clean, wpm=200), 10.0)
    check("talks_too_fast insight",
          any(i.insight_type == InsightType.TALKS_TOO_FAST for i in r_fast.insights))

    # Multi-word filler
    mwf = "you know I think you know this is kind of important you know"
    r_mwf = fluency_mod.analyze(_tr(mwf, wpm=140), 15.0)
    check("multi-word filler detected",   "you know" in r_mwf.filler_events, r_mwf.filler_events)

    # Pause count
    segs_with_pause = [_seg(0.0, 1.0, 0.9), _seg(2.5, 4.0, 0.9)]  # gap = 1.5 s
    r_pause = fluency_mod.analyze(_tr(clean, wpm=140, segments=segs_with_pause), 30.0)
    check("pause counted",                r_pause.metrics["pause_count"] == 1)


    print("\n── T3  Clarity ─────────────────────────────────────────")

    # Repeated phrases
    rep = "I think the product is great. I think the product is great. I think the product is great."
    r = clarity_mod.analyze(_tr(rep), 30.0)
    check("dimension == CLARITY",           r.dimension == Dimension.CLARITY)
    check("repeated phrases detected",      r.metrics["repeated_phrase_count"] > 0)
    check("score < 70 (high repetition)",   r.score < 70.0,  r.score)

    # Clean varied text
    clean2 = "The pipeline runs in five stages. Each stage produces an immutable contract."
    r_clean = clarity_mod.analyze(_tr(clean2), 20.0)
    check("clean clarity > 60",             r_clean.score > 60.0, r_clean.score)
    check("no topic drift on short text",   not r_clean.metrics["topic_drift"])


    print("\n── T4  Expression ──────────────────────────────────────")

    # Rich vocabulary — all unique, long words
    rich = ("The implementation leverages asynchronous processing and modular abstraction "
            "to achieve deterministic reproducibility across architectural boundaries.")
    r = expression_mod.analyze(_tr(rich), 30.0)
    check("dimension == EXPRESSION",    r.dimension == Dimension.EXPRESSION)
    check("high expression score",      r.score > 60.0, r.score)
    check("strong_vocabulary insight",
          any(i.insight_type == InsightType.STRONG_VOCABULARY for i in r.insights))

    # Repetitive vocabulary
    poor = " ".join(["good"] * 20)
    r_poor = expression_mod.analyze(_tr(poor), 10.0)
    check("low expression score",       r_poor.score < 40.0, r_poor.score)
    check("no strong_vocab insight",
          not any(i.insight_type == InsightType.STRONG_VOCABULARY for i in r_poor.insights))


    print("\n── T5  Speech Signal Clarity ───────────────────────────")

    hi_segs = [_seg(float(i), float(i+1), 0.92) for i in range(5)]
    r = ssc_mod.analyze(_tr("hello", segments=hi_segs), 5.0)
    check("dimension == SSC",            r.dimension == Dimension.SPEECH_SIGNAL_CLARITY)
    check("high ssc score",              r.score > 80.0,  r.score)
    check("no low_signal insight",       len(r.insights) == 0)

    lo_segs = [_seg(float(i), float(i+1), 0.40) for i in range(5)]
    r_lo = ssc_mod.analyze(_tr("hello", segments=lo_segs), 5.0)
    check("low ssc score",               r_lo.score < 50.0, r_lo.score)
    check("low_signal_clarity insight",
          any(i.insight_type == InsightType.LOW_SIGNAL_CLARITY for i in r_lo.insights))


    print("\n── T6  Conciseness ─────────────────────────────────────")

    verbose = (
        "In order to make progress, due to the fact that we need results, "
        "at this point in time I just wanted to say that basically what happened was "
        "in order to move forward."
    )
    r = conciseness_mod.analyze(_tr(verbose), 15.0)
    check("dimension == CONCISENESS",    r.dimension == Dimension.CONCISENESS)
    check("verbose phrases ≥ 2",         r.metrics["verbose_phrase_count"] >= 2)
    check("verbose_phrases insight",
          any(i.insight_type == InsightType.VERBOSE_PHRASES for i in r.insights))
    check("score penalised by verbosity",  r.score < 82.0, r.score)

    # Repeated ideas — nearly identical sentences
    rep_ideas = (
        "The pipeline is fast and reliable. "
        "The pipeline is fast and reliable. "
        "Something entirely different happened."
    )
    r_rep = conciseness_mod.analyze(_tr(rep_ideas), 15.0)
    check("repeated idea detected",      r_rep.metrics["repeated_idea_count"] > 0,
          r_rep.metrics["repeated_idea_count"])
    check("repeated_ideas insight",
          any(i.insight_type == InsightType.REPEATED_IDEAS for i in r_rep.insights))

    # Clean concise text
    clean3 = "Each stage returns an immutable contract. The pipeline is sequential."
    r_clean = conciseness_mod.analyze(_tr(clean3), 10.0)
    check("clean conciseness > 60",      r_clean.score > 60.0, r_clean.score)


    print("\n── T7  run_all aggregator ──────────────────────────────")

    text = (
        "Um basically I think the system works well but you know "
        "I think we should probably um consider the performance characteristics."
    )
    segs = [_seg(i * 2.0, i * 2.0 + 1.5, 0.80) for i in range(6)]
    bundle = run_all(_tr(text, wpm=150, segments=segs), 30.0)

    check("5 dimensions returned",       len(bundle.dimensions) == 5)
    check("overall_score in [0, 100]",   0 <= bundle.overall_score <= 100, bundle.overall_score)
    check("first dimension is FLUENCY",  bundle.dimensions[0].dimension == Dimension.FLUENCY)
    check("all dimensions present",
          {d.dimension for d in bundle.dimensions} == set(Dimension))

    expected = round(
        sum(d.score * WEIGHTS[d.dimension] for d in bundle.dimensions), 1
    )
    check("overall == weighted sum",     bundle.overall_score == expected,
          f"got {bundle.overall_score}, expected {expected}")

    print("\n✓  All tests passed. Phase 4 complete.\n")


if __name__ == "__main__":
    run()