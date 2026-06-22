"""
Stage 2 — Speech-to-text.
Backend-agnostic interface: swap local Whisper for an API by changing one config value.

CRITICAL IMPLEMENTATION NOTE
faster-whisper's model.transcribe() returns a lazy generator.
The generator MUST be fully materialised into a tuple BEFORE del model is called.
Freeing the model while the generator is still unconsumed produces silent empty output.
The `finally` block in LocalWhisperTranscriber enforces the correct order.
"""
from __future__ import annotations

import gc
import logging
from abc import ABC, abstractmethod

from core.contracts import RecordingResult, Segment, TranscriptionResult, Word

logger = logging.getLogger(__name__)


class TranscriptionError(Exception):
    """Raised when STT fails to load, transcribe, or parse output."""


# ---------------------------------------------------------------------------
# Backend interface
# ---------------------------------------------------------------------------

class Transcriber(ABC):
    """
    All STT backends implement this interface.
    Implementations MUST be stateless between calls and MUST free all model
    memory before returning.
    """

    @abstractmethod
    def transcribe(self, recording: RecordingResult) -> TranscriptionResult:
        ...


# ---------------------------------------------------------------------------
# Local Whisper backend (v1 default)
# ---------------------------------------------------------------------------

class LocalWhisperTranscriber(Transcriber):
    """
    Runs faster-whisper on CPU with int8 quantisation.
    The model is loaded immediately before inference and freed immediately after.
    Peak RAM: ~350 MB (base) or ~500 MB (small). Idle: ~50 MB.
    """

    def __init__(self, model_size: str = "base") -> None:
        self._model_size = model_size
        # Model is NOT loaded here — load on demand, free after use.

    def transcribe(self, recording: RecordingResult) -> TranscriptionResult:
        """
        Load → transcribe → materialise segments → free model → return contract.
        The generator materialisation step is non-negotiable: see module docstring.
        """
        logger.info("Loading Whisper '%s'…", self._model_size)

        try:
            from faster_whisper import WhisperModel
            model = WhisperModel(
                self._model_size,
                device="cpu",
                compute_type="int8",
            )
        except Exception as exc:
            raise TranscriptionError(
                f"Failed to load Whisper model '{self._model_size}': {exc}"
            ) from exc

        try:
            raw_segments, _info = model.transcribe(
                recording.wav_path,
                beam_size=5,
                language=None,        # auto-detect
                vad_filter=True,      # suppress hallucinations on silence
                word_timestamps=True, # v1.5
            )

            # ── MATERIALISE THE GENERATOR NOW ───────────────────────────
            # Do not move this loop below the `finally` block.
            segments_list: list[Segment] = []
            words_list:    list[Word]    = []
            text_parts:    list[str]     = []

            for seg in raw_segments:
                # Normalise avg_logprob to [0, 1].
                # Segment.__post_init__ clamps the result.
                confidence = 1.0 + seg.avg_logprob / 5.0
                segments_list.append(Segment(
                    start=seg.start, end=seg.end,
                    text=seg.text, confidence=confidence,
                ))
                text_parts.append(seg.text)
                if seg.words:
                    for w in seg.words:
                        words_list.append(Word(
                            word=w.word, start=w.start,
                            end=w.end, probability=w.probability,
                        ))

            segments: tuple[Segment, ...] = tuple(segments_list)
            words:    tuple[Word, ...]    = tuple(words_list)

        except TranscriptionError:
            raise
        except Exception as exc:
            raise TranscriptionError(f"Transcription failed: {exc}") from exc
        finally:
            # Free model memory regardless of success or failure.
            # The generator is already materialised above, so this is safe.
            del model
            gc.collect()
            logger.info("Whisper model freed.")

        # Build the flat transcript from materialised segments
        full_text  = "".join(text_parts).strip()
        word_count = len(full_text.split()) if full_text else 0
        wpm        = (
            round(word_count / recording.duration_seconds * 60, 1)
            if recording.duration_seconds > 0 else 0.0
        )

        logger.info(
            "Transcription complete: %d words, %.1f WPM, %d segments",
            word_count, wpm, len(segments),
        )

        return TranscriptionResult(
            text=full_text,
            segments=segments,
            word_count=word_count,
            speaking_rate_wpm=wpm,
            words=words,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_transcriber(config) -> Transcriber:
    """
    Returns the correct Transcriber based on config.TRANSCRIPTION_BACKEND.
    Switching backends requires only a config change — no structural changes elsewhere.
    """
    backend = config.TRANSCRIPTION_BACKEND

    if backend == "local":
        return LocalWhisperTranscriber(model_size=config.WHISPER_MODEL)

    if backend == "openai":
        raise NotImplementedError(
            "OpenAI Whisper API backend is planned for v1.5. "
            "Set TRANSCRIPTION_BACKEND=local to use the local model."
        )

    raise ValueError(
        f"Unknown transcription backend: '{backend}'. "
        f"Valid options: 'local', 'openai'."
    )