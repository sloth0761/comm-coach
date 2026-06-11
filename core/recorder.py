"""
Stage 1 — Audio recording.
Streams microphone input directly to a WAV file. No audio is buffered in RAM
beyond the current write chunk. Memory usage at this stage is near zero.
"""
from __future__ import annotations

import gc
import logging
import time
import wave
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd

from core.contracts import RecordingResult

logger = logging.getLogger(__name__)


class RecorderError(Exception):
    """Raised when the recorder cannot start or encounters a hardware problem."""


class AudioRecorder:
    """
    Records microphone input to a 16 kHz / 16-bit / mono WAV file.

    Lifecycle:
        recorder = AudioRecorder(output_dir)
        recorder.start()          # opens device + WAV file
        ... (recording in progress) ...
        result = recorder.stop()  # closes both, returns RecordingResult
    """

    def __init__(self, output_dir: str, sample_rate: int = 16_000) -> None:
        self._output_dir  = Path(output_dir)
        self._sample_rate = sample_rate
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._stream:        sd.InputStream | None  = None
        self._wav_file:      wave.Wave_write | None = None
        self._wav_path:      str | None             = None
        self._frames_written: int                   = 0
        self._start_time:    float | None           = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Open the default microphone and begin streaming to disk.
        Raises RecorderError if already recording or if no input device is found.
        """
        if self._stream is not None:
            raise RecorderError("Already recording. Call stop() before start().")

        # Prepare WAV file
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._wav_path = str(self._output_dir / f"{ts}.wav")
        self._wav_file = wave.open(self._wav_path, "wb")
        self._wav_file.setnchannels(1)
        self._wav_file.setsampwidth(2)          # 16-bit = 2 bytes per sample
        self._wav_file.setframerate(self._sample_rate)
        self._frames_written = 0

        # Open sounddevice stream
        try:
            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=1,
                dtype="int16",
                blocksize=1024,
                callback=self._callback,
            )
            self._stream.start()
            self._start_time = time.monotonic()
            logger.info("Recording started → %s", self._wav_path)

        except sd.PortAudioError as exc:
            # Clean up the WAV file we already opened
            self._wav_file.close()
            self._wav_file = None
            self._wav_path = None
            raise RecorderError(f"Could not open microphone: {exc}") from exc

    def stop(self) -> RecordingResult:
        """
        Stop recording, flush and close the WAV file.
        Returns a RecordingResult. Duration is computed from frames written,
        not wall-clock time, so it is exact even under CPU load.
        Raises RecorderError if not currently recording.
        """
        if self._stream is None:
            raise RecorderError("Not currently recording.")

        # Stop + close the stream — blocks until the last callback returns
        self._stream.stop()
        self._stream.close()
        self._stream = None

        # Flush and close the WAV file
        self._wav_file.close()
        self._wav_file = None

        duration  = self._frames_written / self._sample_rate
        wav_path  = self._wav_path
        self._wav_path     = None
        self._start_time   = None
        self._frames_written = 0

        logger.info("Recording stopped. Duration: %.1f s, path: %s", duration, wav_path)

        return RecordingResult(
            wav_path=wav_path,
            duration_seconds=duration,
            created_at=datetime.now(),
            sample_rate=self._sample_rate,
        )

    # ------------------------------------------------------------------
    # Properties (used by the UI to drive the elapsed-time counter)
    # ------------------------------------------------------------------

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    @property
    def elapsed_seconds(self) -> float:
        """Monotonic elapsed time since start(). Returns 0.0 when idle."""
        if self._start_time is None:
            return 0.0
        return time.monotonic() - self._start_time

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        """
        sounddevice audio callback. Runs in a dedicated audio thread.
        Only job: write raw bytes to the WAV file.
        """
        if status:
            logger.warning("Recorder status flag: %s", status)
        if self._wav_file is not None:
            # indata shape: (frames, 1) — tobytes() is safe for mono WAV PCM
            self._wav_file.writeframes(indata.tobytes())
            self._frames_written += frames