"""
Stage 4 — Coaching.
Backend-agnostic interface. LocalLLMCoach is implemented in Phase 7.
DummyCoach provides deterministic, analytics-derived feedback so the full
pipeline runs and can be validated before SmolLM is wired.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod

from core.contracts import AnalyticsBundle, CoachingResult, MemoryContext

logger = logging.getLogger(__name__)


class CoachingError(Exception):
    """Raised when the coaching stage fails and cannot produce a fallback."""


# ---------------------------------------------------------------------------
# Backend interface
# ---------------------------------------------------------------------------

class Coach(ABC):
    """
    All coaching backends implement this interface.
    Implementations must free all model memory before returning.
    """

    @abstractmethod
    def coach(
        self,
        transcript: str,
        analytics: AnalyticsBundle,
        context: MemoryContext,
    ) -> CoachingResult: ...


# ---------------------------------------------------------------------------
# DummyCoach — deterministic, no LLM (Phase 6)
# ---------------------------------------------------------------------------

class DummyCoach(Coach):
    """
    Derives coaching feedback entirely from analytics scores.
    Used during development and as the pipeline fallback when the LLM fails.
    Replaced by LocalLLMCoach in Phase 7 with zero pipeline changes.
    """

    def coach(
        self,
        transcript: str,
        analytics: AnalyticsBundle,
        context: MemoryContext,
    ) -> CoachingResult:
        dims     = {d.dimension: d for d in analytics.dimensions}
        weakest  = min(dims.values(), key=lambda d: d.score)
        strongest = max(dims.values(), key=lambda d: d.score)

        assessment = (
            f"Session score: {analytics.overall_score:.0f}/100 "
            f"(analytics-only — LLM not yet enabled). "
            f"Strongest: {strongest.dimension} ({strongest.score:.0f}). "
            f"Needs work: {weakest.dimension} ({weakest.score:.0f})."
        )
        key_insight = f"Your {weakest.dimension} score of {weakest.score:.0f} is your lowest this session."
        next_focus  = weakest.feedback

        raw = json.dumps({
            "overall_assessment": assessment,
            "strengths":   [strongest.feedback],
            "improvements": [weakest.feedback],
            "key_insight": key_insight,
            "next_focus":  next_focus,
        })

        return CoachingResult(
            overall_assessment=assessment,
            strengths=(strongest.feedback,),
            improvements=(weakest.feedback,),
            key_insight=key_insight,
            next_focus=next_focus,
            raw_json=raw,
        )


# ---------------------------------------------------------------------------
# LocalLLMCoach — SmolLM2 via llama-cpp-python (Phase 7)
# ---------------------------------------------------------------------------

class LocalLLMCoach(Coach):
    """
    SmolLM2-1.7B-Instruct via llama-cpp-python.
    Load → call → free. Never kept resident between sessions.
    Full implementation in Phase 7.
    """

    def __init__(self, model_path: str, n_ctx: int = 4096) -> None:
        self._model_path = model_path
        self._n_ctx      = n_ctx

    def coach(
        self,
        transcript: str,
        analytics: AnalyticsBundle,
        context: MemoryContext,
    ) -> CoachingResult:
        raise NotImplementedError(
            "LocalLLMCoach is implemented in Phase 7. "
            "Place the SmolLM2 GGUF in data/models/ and re-run."
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_coach(config) -> Coach:
    """
    Returns the correct Coach based on config.COACHING_BACKEND.
    Falls back to DummyCoach if the GGUF file is missing (development convenience).
    """
    backend = config.COACHING_BACKEND

    if backend == "local":
        from pathlib import Path
        if not Path(config.LLAMA_MODEL_PATH).exists():
            logger.warning(
                "GGUF model not found at '%s'. Using DummyCoach until Phase 7.",
                config.LLAMA_MODEL_PATH,
            )
            return DummyCoach()
        return LocalLLMCoach(model_path=config.LLAMA_MODEL_PATH)

    if backend in ("claude", "openai"):
        raise NotImplementedError(
            f"Cloud coaching backend '{backend}' is planned for v1.5."
        )

    raise ValueError(
        f"Unknown coaching backend: '{backend}'. "
        f"Valid options: 'local', 'claude', 'openai'."
    )