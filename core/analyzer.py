"""
Stage 4 — Coaching.
Backend-agnostic interface.

LocalLLMCoach: SmolLM2-1.7B via llama-cpp-python.
Load → prompt → parse JSON → free. One retry on bad output. Fallback to
DummyCoach if both attempts fail — analytics scores are never lost.

DummyCoach: deterministic fallback derived from analytics scores.
Used as the development stub (Phase 6) and as the runtime fallback.
"""
from __future__ import annotations

import gc
import json
import logging
import os
import re
from abc import ABC, abstractmethod

from core.contracts import AnalyticsBundle, CoachingResult, MemoryContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt constants  (PRD §9)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a professional communication coach with access to this speaker's "
    "full session history. Analyse the transcript, the current analytics scores, "
    "and the historical context provided. "
    "Respond ONLY with a valid JSON object — no preamble, no explanation, "
    "no markdown fences."
)

_FORMAT_REMINDER = """\
Return ONLY this JSON object (no other text):
{
  "overall_assessment": "2-3 sentence honest assessment of this specific session",
  "strengths": ["specific strength 1", "specific strength 2"],
  "improvements": ["specific improvement 1", "specific improvement 2"],
  "key_insight": "one memorable, actionable observation unique to this speaker",
  "next_focus": "one concrete thing to practise before the next session"
}"""

_REPAIR_PROMPT = (
    "Your previous response was not valid JSON or was missing required fields. "
    "Return ONLY a valid JSON object with exactly these five keys: "
    "overall_assessment (string), strengths (array of strings), "
    "improvements (array of strings), key_insight (string), next_focus (string). "
    "No preamble. No markdown. Just the JSON."
)

_REQUIRED_KEYS: dict[str, type] = {
    "overall_assessment": str,
    "strengths":          list,
    "improvements":       list,
    "key_insight":        str,
    "next_focus":         str,
}


class CoachingError(Exception):
    """Raised when coaching fails and no fallback is possible."""


# ---------------------------------------------------------------------------
# Backend interface
# ---------------------------------------------------------------------------

class Coach(ABC):
    @abstractmethod
    def coach(
        self,
        transcript: str,
        analytics: AnalyticsBundle,
        context: MemoryContext,
    ) -> CoachingResult: ...


# ---------------------------------------------------------------------------
# DummyCoach — deterministic, no LLM
# ---------------------------------------------------------------------------

class DummyCoach(Coach):
    """
    Derives coaching feedback entirely from analytics scores.
    Development stub and runtime fallback — zero pipeline changes when replaced.
    """

    def coach(
        self,
        transcript: str,
        analytics: AnalyticsBundle,
        context: MemoryContext,
    ) -> CoachingResult:
        dims      = {d.dimension: d for d in analytics.dimensions}
        weakest   = min(dims.values(), key=lambda d: d.score)
        strongest = max(dims.values(), key=lambda d: d.score)

        assessment = (
            f"Session score: {analytics.overall_score:.0f}/100 "
            f"(analytics-only feedback). "
            f"Strongest area: {strongest.dimension} ({strongest.score:.0f}). "
            f"Needs most work: {weakest.dimension} ({weakest.score:.0f})."
        )
        key_insight = (
            f"Your {weakest.dimension} score of {weakest.score:.0f} "
            "is your lowest this session."
        )

        raw = json.dumps({
            "overall_assessment": assessment,
            "strengths":          [strongest.feedback],
            "improvements":       [weakest.feedback],
            "key_insight":        key_insight,
            "next_focus":         weakest.feedback,
        })

        return CoachingResult(
            overall_assessment=assessment,
            strengths=(strongest.feedback,),
            improvements=(weakest.feedback,),
            key_insight=key_insight,
            next_focus=weakest.feedback,
            raw_json=raw,
        )


# ---------------------------------------------------------------------------
# LocalLLMCoach — SmolLM2-1.7B via llama-cpp-python
# ---------------------------------------------------------------------------

class LocalLLMCoach(Coach):
    """
    Runs SmolLM2-1.7B-Instruct (Q4_K_M GGUF) via llama-cpp-python.
    The model is loaded immediately before inference and freed immediately after.
    Peak RAM: ~1.2 GB. Idle: ~50 MB.

    Failure behaviour:
      • Bad JSON on first attempt  → one repair prompt at lower temperature
      • Bad JSON on second attempt → DummyCoach fallback (session still saved)
      • Model load failure         → DummyCoach fallback
    The pipeline never crashes on LLM output problems.
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
        from llama_cpp import Llama

        llm = None
        try:
            logger.info("Loading SmolLM2 from %s …", self._model_path)
            llm = Llama(
                model_path=self._model_path,
                n_ctx=self._n_ctx,
                n_threads=os.cpu_count() or 4,
                verbose=False,
            )

            messages = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": context.rendered + "\n\n" + _FORMAT_REMINDER},
            ]

            # ── First attempt ─────────────────────────────────────────────
            raw = _call(llm, messages, temperature=0.4, max_tokens=512)
            logger.debug("Raw LLM output:\n%s", raw)

            try:
                return _parse(raw)

            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                logger.warning("Parse failed (%s). Sending repair prompt.", exc)

                # ── Repair attempt ────────────────────────────────────────
                repair_messages = [
                    *messages,
                    {"role": "assistant", "content": raw},
                    {"role": "user",      "content": _REPAIR_PROMPT},
                ]
                raw2 = _call(llm, repair_messages, temperature=0.2, max_tokens=512)
                logger.debug("Repair LLM output:\n%s", raw2)

                try:
                    return _parse(raw2)
                except Exception as exc2:
                    logger.warning(
                        "Repair also failed (%s). Falling back to analytics.", exc2
                    )
                    return DummyCoach().coach(transcript, analytics, context)

        except Exception as exc:
            logger.warning("LLM error (%s). Falling back to analytics.", exc)
            return DummyCoach().coach(transcript, analytics, context)

        finally:
            if llm is not None:
                del llm
                gc.collect()
                logger.info("SmolLM2 freed.")


# ---------------------------------------------------------------------------
# Module-level helpers (importable for direct unit testing)
# ---------------------------------------------------------------------------

def _call(llm, messages: list[dict], temperature: float, max_tokens: int) -> str:
    """Call the model and return the raw content string."""
    response = llm.create_chat_completion(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    return response["choices"][0]["message"]["content"]


def _parse(raw: str) -> CoachingResult:
    """
    Parse and validate a raw LLM string into a CoachingResult.
    Strips markdown fences if the model added them despite instructions.
    Raises ValueError / json.JSONDecodeError on any problem.
    """
    text = raw.strip()

    # Strip accidental ``` fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$",       "", text)
        text = text.strip()

    data = json.loads(text)

    for key, typ in _REQUIRED_KEYS.items():
        if key not in data:
            raise ValueError(f"Missing key: '{key}'")
        if not isinstance(data[key], typ):
            raise ValueError(
                f"Key '{key}' must be {typ.__name__}, "
                f"got {type(data[key]).__name__}"
            )
        if isinstance(data[key], str) and not data[key].strip():
            raise ValueError(f"Key '{key}' is an empty string")

    return CoachingResult(
        overall_assessment=data["overall_assessment"].strip(),
        strengths=tuple(str(s).strip() for s in data["strengths"]  if str(s).strip()),
        improvements=tuple(str(s).strip() for s in data["improvements"] if str(s).strip()),
        key_insight=data["key_insight"].strip(),
        next_focus=data["next_focus"].strip(),
        raw_json=json.dumps(data),
    )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_coach(config) -> Coach:
    """
    Returns the correct Coach based on config.COACHING_BACKEND.
    Falls back to DummyCoach when the GGUF file is not yet present.
    """
    backend = config.COACHING_BACKEND

    if backend == "local":
        from pathlib import Path
        if not Path(config.LLAMA_MODEL_PATH).exists():
            logger.warning(
                "GGUF not found at '%s'. Using DummyCoach.", config.LLAMA_MODEL_PATH
            )
            return DummyCoach()
        return LocalLLMCoach(model_path=config.LLAMA_MODEL_PATH)

    if backend in ("claude", "openai"):
        raise NotImplementedError(
            f"Cloud coaching backend '{backend}' is planned for v1.5."
        )

    raise ValueError(
        f"Unknown coaching backend: '{backend}'. Valid: 'local', 'claude', 'openai'."
    )