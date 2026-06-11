"""
Threshold constants for all five analytics modules.
Tune here after real-world testing — never hardcode thresholds in module files.
"""

# ── Fluency ───────────────────────────────────────────────────────────────
OVERUSES_FILLER_MIN    = 4      # same filler word ≥ N times in one session
TALKS_TOO_FAST_WPM     = 180    # WPM at or above this triggers the insight

# ── Expression ────────────────────────────────────────────────────────────
STRONG_VOCAB_TTR       = 0.65   # content-word TTR ≥ this → strong vocabulary

# ── Speech Signal Clarity ─────────────────────────────────────────────────
LOW_SIGNAL_CONF        = 0.55   # segments below this confidence are low-quality
LOW_SIGNAL_SEGMENTS_MIN = 3     # ≥ this many low-confidence segments → insight

# ── Conciseness ───────────────────────────────────────────────────────────
VERBOSE_PHRASES_MIN    = 2      # verbose phrase occurrences before insight fires
REPEATED_IDEAS_MIN     = 1      # repeated sentence pairs before insight fires

# ── Clarity ───────────────────────────────────────────────────────────────
TOPIC_DRIFT_OVERLAP    = 0.10   # Jaccard overlap < this → topic drift detected