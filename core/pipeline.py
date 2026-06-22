"""
Pipeline orchestrator — coordinates Stages 2–5 for one recorded session.
Stage 1 (recording) is handled by the UI layer; the result is passed in here.

Design rules:
  • Holds no models. Constructed once at app start.
  • All model loading/freeing happens inside each stage's own module.
  • Analytics scores are never lost because coaching failed.
  • on_stage callback drives the UI status bar without coupling to PyQt.
"""
from __future__ import annotations

import enum
import logging
from typing import Callable

from core.contracts import RecordingResult, SessionResult
from core.memory import MemoryStore
from core.memory_engine import MemoryEngine

logger = logging.getLogger(__name__)


class PipelineStage(enum.Enum):
    TRANSCRIBING      = "Transcribing"
    ANALYZING         = "Analyzing"
    ASSEMBLING_MEMORY = "Assembling memory"
    COACHING          = "Coaching"
    SAVING            = "Saving"
    EMBEDDING         = "Embedding"
    DONE              = "Done"


class PipelineError(Exception):
    """Raised when a session cannot be completed (e.g. transcript too short)."""


class SessionPipeline:
    """
    Runs Stages 2–5 sequentially for one RecordingResult.

    Wiring (done once in main.py):
        pipeline = SessionPipeline(
            transcriber = make_transcriber(config),
            coach       = make_coach(config),
            store       = MemoryStore(config.DB_PATH),
            engine      = MemoryEngine(store),
            on_stage    = self.status_bar.update,
        )
    """

    def __init__(
        self,
        transcriber,
        coach,
        store: MemoryStore,
        engine: MemoryEngine,
        embedder=None,
        on_stage: Callable[[PipelineStage], None] = lambda _: None,
    ) -> None:
        self._transcriber = transcriber
        self._coach       = coach
        self._store       = store
        self._engine      = engine
        self._embedder    = embedder
        self._on_stage    = on_stage

    def set_on_stage(self, callback: Callable[[PipelineStage], None]) -> None:
        self._on_stage = callback

    def run(self, recording: RecordingResult) -> SessionResult:
        """
        Execute Stages 2–5 in order and return a SessionResult for the UI.

        Failure modes:
          • Transcript < 10 words  → raises PipelineError (session not saved)
          • Coaching fails          → falls back to DummyCoach, session still saved
          • SQLite write fails      → raises StorageError (caller should show retry)
        """
        # Imported here to keep startup fast and avoid any circular-import risk.
        from analytics import run_all
        from core.analyzer import DummyCoach

        # ── Stage 2 — Transcribe ──────────────────────────────────────────
        self._on_stage(PipelineStage.TRANSCRIBING)
        logger.info("Stage 2: transcribing %s", recording.wav_path)
        transcription = self._transcriber.transcribe(recording)

        if transcription.word_count < 10:
            raise PipelineError(
                f"Transcript too short ({transcription.word_count} words). "
                "Please record at least a few sentences."
            )

        # ── Stage 3 — Analytics ───────────────────────────────────────────
        self._on_stage(PipelineStage.ANALYZING)
        logger.info("Stage 3: analytics")
        analytics = run_all(transcription, recording.duration_seconds)

        # ── Stage 4a — Memory assembly ────────────────────────────────────
        self._on_stage(PipelineStage.ASSEMBLING_MEMORY)
        logger.info("Stage 4a: assembling memory context")
        context = self._engine.assemble_context(
            analytics, transcription.text, embedder=self._embedder
        )

        # ── Stage 4b — Coaching ───────────────────────────────────────────
        self._on_stage(PipelineStage.COACHING)
        logger.info("Stage 4b: coaching")
        try:
            coaching = self._coach.coach(transcription.text, analytics, context)
        except Exception as exc:
            # Analytics are valid — don't discard the session just because the
            # LLM misbehaved. Log and fall back to deterministic feedback.
            logger.warning("Coaching failed (%s). Using DummyCoach fallback.", exc)
            coaching = DummyCoach().coach(transcription.text, analytics, context)

        # ── Stage 5 — Save + Profile ──────────────────────────────────────
        self._on_stage(PipelineStage.SAVING)
        logger.info("Stage 5: saving session")
        session_id = self._store.save_session(recording, transcription, analytics, coaching)

        # ── Stage 5b — embed (optional, non-blocking) ──────────────────────
        if self._embedder is not None:
            self._on_stage(PipelineStage.EMBEDDING)
            try:
                vec = self._embedder.embed(transcription.text)
                self._store.save_embedding(session_id, vec, self._embedder.model_name)
            except Exception as exc:
                logger.warning("Embedding failed (%s). Skipping.", exc)

        profile = self._engine.generate_profile()

        # ── Stage 5d — narrative (optional second LLM load) ────────────────
        from dataclasses import replace as _replace
        try:
            narrative = self._coach.generate_narrative(profile)
            if narrative:
                profile = _replace(profile, narrative=narrative)
        except Exception as exc:
            logger.warning("Narrative error (%s). Skipping.", exc)

        self._on_stage(PipelineStage.DONE)
        logger.info("Pipeline complete. session_id=%d", session_id)

        return SessionResult(
            session_id=session_id,
            recording=recording,
            transcription=transcription,
            analytics=analytics,
            coaching=coaching,
            profile=profile,
        )