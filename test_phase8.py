"""
Standalone validation for Phase 8: UI components, worker signals, state machine.
Run from project root:
    QT_QPA_PLATFORM=offscreen python tests/test_phase8.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

# Must be set BEFORE QApplication is created
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Minimal fakes (no Whisper, no SmolLM2)
# ---------------------------------------------------------------------------

from core.contracts import (
    AnalyticsBundle, CoachingResult, CommunicationProfile, Dimension,
    DimensionResult, Insight, InsightType, MemoryContext, RecordingResult,
    Segment, SessionResult, TranscriptionResult,
)
from core.transcriber import Transcriber
from core.analyzer import Coach
from core.pipeline import SessionPipeline, PipelineStage


def _fake_dim(dim: Dimension, score: float = 72.0) -> DimensionResult:
    return DimensionResult(
        dimension=dim, score=score,
        metrics={
            "filler_count": 3, "filler_rate_per_100": 2.1,
            "wpm": 148.0, "pause_count": 2, "filler_score": 79.0, "wpm_score": 100.0,
            "repeated_phrase_count": 1, "avg_sentence_length": 14.2, "sentence_count": 8,
            "topic_drift": False, "repetition_penalty": 12.0, "drift_penalty": 0.0,
            "sentence_length_score": 100.0,
            "corrected_ttr": 0.71, "unique_content_words": 38, "total_content_words": 53,
            "complex_word_ratio": 0.12, "avg_content_word_length": 5.4,
            "diversity_score": 71.0, "complexity_score": 30.0,
            "avg_confidence": 0.84, "low_confidence_segments": 1, "segment_count": 12,
            "verbose_phrase_count": 1, "repeated_idea_count": 0, "content_word_density": 0.47,
            "verbose_penalty": 5.0, "idea_penalty": 0.0, "density_score": 94.0,
        },
        feedback="Good job.",
        insights=(Insight(InsightType.OVERUSES_FILLER, "um"),),
        filler_events={"um": 3} if dim == Dimension.FLUENCY else {},
    )


def _fake_session_result(session_id: int = 1) -> SessionResult:
    dims = tuple(_fake_dim(d, 68.0 + i * 4) for i, d in enumerate(Dimension))
    analytics = AnalyticsBundle(dimensions=dims, overall_score=72.5)
    coaching = CoachingResult(
        overall_assessment="Solid session. Good pacing, watch filler words.",
        strengths=("Clear sentence structure",),
        improvements=("Reduce 'um' usage",),
        key_insight="You use 'um' as a thinking pause. Try a silent pause instead.",
        next_focus="Record 60 seconds with zero filler words.",
        raw_json="{}",
    )
    profile = CommunicationProfile(
        strengths=("fluency (avg 76)",),
        recurring_weaknesses=("overuses_filler (3 sessions)",),
        trends={str(d): "stable" for d in Dimension},
        persistent_fillers=({"word": "um", "sessions_with": 3, "total": 18},),
        notable_pattern='"um" appears in 3 of 3 sessions (6.0 per session).',
    )
    recording = RecordingResult(
        wav_path="/tmp/fake.wav", duration_seconds=30.0, created_at=datetime.now()
    )
    transcription = TranscriptionResult(
        text="Um basically I think this is a solid session.",
        segments=(Segment(0.0, 5.0, "Um basically", 0.84),),
        word_count=9, speaking_rate_wpm=148.0,
    )
    return SessionResult(
        session_id=session_id,
        recording=recording,
        transcription=transcription,
        analytics=analytics,
        coaching=coaching,
        profile=profile,
    )


class _FakePipeline:
    def __init__(self, result: SessionResult | None = None, raises: str | None = None):
        self._result = result or _fake_session_result()
        self._raises = raises
        self._on_stage = lambda _: None

    def run(self, recording):
        for stage in PipelineStage:
            self._on_stage(stage)
        if self._raises:
            raise RuntimeError(self._raises)
        return self._result


class _FakeRecorder:
    def __init__(self):
        self.started = False
        self.elapsed_seconds = 0.0

    def start(self):
        self.started = True

    def stop(self):
        return RecordingResult(
            wav_path="/tmp/fake.wav",
            duration_seconds=5.0,
            created_at=datetime.now(),
        )

    @property
    def is_recording(self):
        return self.started


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def run() -> None:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    print("\n── T1  UI module imports ───────────────────────────────")
    from ui.theme import STYLESHEET, score_color, score_bg
    from ui.widgets import ScoreCard, MetricRow, SectionHeader, FillerTagRow
    from ui.app import MainWindow, PipelineWorker
    check("theme imports",   bool(STYLESHEET))
    check("widgets import",  True)
    check("app imports",     True)


    print("\n── T2  score_color thresholds ──────────────────────────")
    check("score 75 → green",  score_color(75) == "#2E7D32")
    check("score 74 → amber",  score_color(74) == "#E65100")
    check("score 50 → amber",  score_color(50) == "#E65100")
    check("score 49 → red",    score_color(49) == "#C62828")
    check("score 0  → red",    score_color(0)  == "#C62828")
    check("score 100 → green", score_color(100) == "#2E7D32")


    print("\n── T3  ScoreCard widget ────────────────────────────────")
    card = ScoreCard("Fluency")
    check("initial text is dash",  card._score_label.text() == "—")
    card.set_score(82.0)
    check("score label updated",   card._score_label.text() == "82")
    card.set_score(45.0)
    check("low score text",        card._score_label.text() == "45")
    card.reset()
    check("reset to dash",         card._score_label.text() == "—")


    print("\n── T4  MetricRow widget ────────────────────────────────")
    row = MetricRow("WPM")
    check("default value dash",   row.value_label.text() == "—")
    row.set_value("148")
    check("value updated",        row.value_label.text() == "148")
    row.set_value("Low", color="#FF0000")
    check("coloured value",       row.value_label.text() == "Low")


    print("\n── T5  FillerTagRow widget ─────────────────────────────")
    tag_row = FillerTagRow()
    tag_row.set_fillers({"um": 8, "basically": 3})
    check("tags populated", tag_row._layout.count() > 1)  # stretch + tags


    print("\n── T6  PipelineWorker — success path ───────────────────")
    from PyQt6.QtCore import QEventLoop

    fake_result = _fake_session_result()
    pipeline    = _FakePipeline(result=fake_result)
    recording   = RecordingResult(wav_path="/tmp/x.wav", duration_seconds=5.0,
                                   created_at=datetime.now())
    worker = PipelineWorker(pipeline, recording)

    stages_seen: list[str] = []
    results_seen: list     = []
    errors_seen:  list     = []

    worker.stage_changed.connect(stages_seen.append)
    worker.finished_ok.connect(results_seen.append)
    worker.failed.connect(errors_seen.append)

    loop = QEventLoop()
    worker.finished.connect(loop.quit)
    worker.start()
    loop.exec()

    check("all 6 stages fired",     len(stages_seen) == 6, str(stages_seen))
    check("TRANSCRIBING first",     stages_seen[0] == PipelineStage.TRANSCRIBING.value)
    check("DONE last",              stages_seen[-1] == PipelineStage.DONE.value)
    check("finished_ok emitted",    len(results_seen) == 1)
    check("result is SessionResult", isinstance(results_seen[0], SessionResult))
    check("no errors",              len(errors_seen) == 0)


    print("\n── T7  PipelineWorker — failure path ───────────────────")
    fail_pipeline = _FakePipeline(raises="Simulated error")
    worker2 = PipelineWorker(fail_pipeline, recording)

    results2: list = []
    errors2:  list = []
    worker2.finished_ok.connect(results2.append)
    worker2.failed.connect(errors2.append)

    loop2 = QEventLoop()
    worker2.finished.connect(loop2.quit)
    worker2.start()
    loop2.exec()

    check("no result on failure",   len(results2) == 0)
    check("failed signal emitted",  len(errors2) == 1)
    check("error message correct",  "Simulated error" in errors2[0])


    print("\n── T8  MainWindow construction ─────────────────────────")
    with tempfile.TemporaryDirectory() as tmp:
        from core.memory import MemoryStore
        store    = MemoryStore(str(Path(tmp) / "db.db"))
        pipeline = _FakePipeline()
        recorder = _FakeRecorder()

        window = MainWindow(pipeline=pipeline, recorder=recorder, store=store)
        check("window created",            window is not None)
        check("8 tabs",                    window._tabs.count() == 8)
        check("session_count_label exists", hasattr(window, "_session_count_label"))
        check("record_btn exists",          hasattr(window, "_record_btn"))
        check("overall_score_label exists", hasattr(window, "_overall_score_label"))
        check("initial count empty",        window._session_count_label.text() == "")
        check("history table 0 rows",       window._history_table.rowCount() == 0)


    print("\n── T9  Tab population from SessionResult ───────────────")
    with tempfile.TemporaryDirectory() as tmp:
        from core.memory import MemoryStore
        store    = MemoryStore(str(Path(tmp) / "db.db"))
        pipeline = _FakePipeline()
        recorder = _FakeRecorder()
        window   = MainWindow(pipeline=pipeline, recorder=recorder, store=store)

        result = _fake_session_result(session_id=1)
        window._populate_all_tabs(result)

        score_text = window._overall_score_label.text()
        check("overall score populated",   score_text == "73" or score_text == "72",  score_text)
        check("assessment populated",      "Solid session" in window._assessment_label.text())
        check("key insight populated",     "um" in window._key_insight_box.text().lower())
        check("next focus populated",      "filler" in window._next_focus_box.text().lower())
        check("transcript populated",      "basically" in window._transcript_label.text())

        fluency_card = window._score_cards[Dimension.FLUENCY]
        check("fluency card has score",    fluency_card._score_label.text() != "—")

        check("profile notable set",
              "sessions" in window._profile_notable.text())


    print("\n── T10  Session count updates ──────────────────────────")
    with tempfile.TemporaryDirectory() as tmp:
        from core.memory import MemoryStore
        store   = MemoryStore(str(Path(tmp) / "db.db"))
        window2 = MainWindow(pipeline=_FakePipeline(), recorder=_FakeRecorder(), store=store)
        check("0 sessions → empty label",  window2._session_count_label.text() == "")

        # Manually insert a fake session to check count update
        from types import SimpleNamespace as NS
        result = _fake_session_result()
        store.save_session(result.recording, result.transcription, result.analytics, result.coaching)
        window2._update_session_count()
        check("1 session → label updated", "1 session" in window2._session_count_label.text())


    print("\n✓  All tests passed. Phase 8 complete.\n")
    print("  Run the app:  python main.py")


if __name__ == "__main__":
    run()