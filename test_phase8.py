"""
tests/test_phase8.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime

os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QTabWidget, QStatusBar, QFrame
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtTest import QSignalSpy

from ui.theme import score_colour
from ui.widgets import PipelineWorker
from ui.app import MainWindow

from core.contracts import (
    RecordingResult,
    Segment,
    TranscriptionResult,
    Insight,
    InsightType,
    Dimension,
    DimensionResult,
    AnalyticsBundle,
    CoachingResult,
    CommunicationProfile,
    SessionResult,
)


# ---------------------------------------------------------
# QApplication
# ---------------------------------------------------------

_app = QApplication.instance()

if _app is None:
    _app = QApplication(sys.argv)


# ---------------------------------------------------------
# Fake Data Builders
# ---------------------------------------------------------


def build_session_result():

    recording = RecordingResult(
        wav_path="/tmp/test.wav",
        duration_seconds=30.0,
        created_at=datetime.now(),
    )

    transcription = TranscriptionResult(
        text="This is a test transcript.",
        segments=(
            Segment(
                start=0.0,
                end=1.0,
                text="hello",
                confidence=0.9,
            ),
        ),
        word_count=5,
        speaking_rate_wpm=150.0,
    )

    dimensions = (
        DimensionResult(
            dimension=Dimension.FLUENCY,
            score=80,
            metrics={
                "filler_count": 2,
                "filler_rate_per_100": 1.5,
                "filler_events": {
                    "um": 2,
                },
                "wpm": 150,
                "pause_count": 3,
                "filler_score": 80,
                "wpm_score": 80,
            },
            feedback="Good fluency",
            insights=(),
            filler_events={
                "um": 2,
            },
        ),
        DimensionResult(
            dimension=Dimension.CLARITY,
            score=75,
            metrics={
                "sentence_count": 3,
                "avg_sentence_length": 10,
                "topic_drift": False,
                "repeated_phrase_count": 0,
            },
            feedback="Good clarity",
            insights=(),
            filler_events={},
        ),
        DimensionResult(
            dimension=Dimension.EXPRESSION,
            score=70,
            metrics={
                "corrected_ttr": 0.50,
                "unique_content_words": 25,
                "complex_word_ratio": 0.15,
                "avg_content_word_length": 5.0,
            },
            feedback="Good expression",
            insights=(),
            filler_events={},
        ),
        DimensionResult(
            dimension=Dimension.SPEECH_SIGNAL_CLARITY,
            score=85,
            metrics={
                "avg_confidence": 0.92,
                "low_confidence_segments": 0,
                "segment_count": 1,
            },
            feedback="Clear signal",
            insights=(),
            filler_events={},
        ),
        DimensionResult(
            dimension=Dimension.CONCISENESS,
            score=65,
            metrics={
                "verbose_phrase_count": 1,
                "repeated_idea_count": 0,
                "content_word_density": 0.60,
            },
            feedback="Mostly concise",
            insights=(),
            filler_events={},
        ),
    )

    analytics = AnalyticsBundle(
        dimensions=dimensions,
        overall_score=75,
    )

    coaching = CoachingResult(
        overall_assessment="Solid communication.",
        strengths=("fluency",),
        improvements=("conciseness",),
        key_insight="You speak clearly.",
        next_focus="Reduce filler words.",
        raw_json="{}",
    )

    profile = CommunicationProfile(
        strengths=("fluency",),
        recurring_weaknesses=(),
        trends={
            "fluency": "improving",
        },
        persistent_fillers=(),
        notable_pattern="Improving fluency.",
    )

    return SessionResult(
        session_id=1,
        recording=recording,
        transcription=transcription,
        analytics=analytics,
        coaching=coaching,
        profile=profile,
    )


# ---------------------------------------------------------
# Fake Pipeline
# ---------------------------------------------------------


class FakePipeline:

    def __init__(self):
        self._on_stage = lambda _: None

    def run(self, recording):

        from core.pipeline import PipelineStage

        for stage in PipelineStage:
            self._on_stage(stage)

        return build_session_result()


class FailingPipeline:

    def __init__(self):
        self._on_stage = lambda _: None

    def run(self, recording):
        raise RuntimeError("boom")


# ---------------------------------------------------------
# Fake Recorder
# ---------------------------------------------------------


class FakeRecorder:

    elapsed_seconds = 0

    def start(self):
        return None

    def stop(self):
        return build_session_result().recording


# ---------------------------------------------------------
# Fake Store
# ---------------------------------------------------------


class FakeStore:

    def session_count(self):
        return 0

    def all_sessions_summary(self):
        return []

    def session_detail(self, session_id):
        return {}


# ---------------------------------------------------------
# Tests
# ---------------------------------------------------------


class ThemeTests(unittest.TestCase):

    def test_score_colour_green(self):
        self.assertEqual(
            score_colour(80),
            "#4CAF50",
        )

    def test_score_colour_amber(self):
        self.assertEqual(
            score_colour(60),
            "#FF9800",
        )

    def test_score_colour_red(self):
        self.assertEqual(
            score_colour(40),
            "#F44336",
        )


class WorkerTests(unittest.TestCase):
    from PyQt6.QtTest import QSignalSpy

    def test_worker_success(self):

        worker = PipelineWorker(
            FakePipeline(),
            object(),
        )

        stage_spy = QSignalSpy(worker.stage_changed)
        result_spy = QSignalSpy(worker.finished_ok)

        worker.start()

        self.assertTrue(result_spy.wait(5000))

        worker.wait()

        self.assertGreater(len(stage_spy), 0)
        self.assertEqual(len(result_spy), 1)


    def test_worker_failure(self):
        worker = PipelineWorker(
            FailingPipeline(),
            object(),
        )

        spy = QSignalSpy(worker.failed)

        worker.start()

        self.assertTrue(
            spy.wait(5000)
        )

        worker.wait()

        self.assertEqual(
            len(spy),
            1,
        )

        self.assertEqual(
            spy[0][0],
            "boom",
        )

class MainWindowTests(unittest.TestCase):

    def test_window_constructs(self):

        window = MainWindow(
            pipeline=FakePipeline(),
            recorder=FakeRecorder(),
            store=FakeStore(),
        )

        self.assertIsNotNone(
            window.session_count_label
        )

        self.assertEqual(
            window.tabs.count(),
            8,
        )

    def test_state_machine(self):

        window = MainWindow(
            pipeline=FakePipeline(),
            recorder=FakeRecorder(),
            store=FakeStore(),
        )

        window.start_recording()

        self.assertEqual(
            window.state,
            "recording",
        )

        window.set_idle_state()

        self.assertEqual(
            window.state,
            "idle",
        )


class HistoryShapeTests(unittest.TestCase):

    def test_history_keys(self):

        sample = {
            "id": 1,
            "created_at": datetime.now(),
            "duration_seconds": 10.0,
            "word_count": 100,
            "speaking_rate_wpm": 140.0,
            "overall_score": 75.0,
        }

        required = {
            "id",
            "created_at",
            "duration_seconds",
            "word_count",
            "speaking_rate_wpm",
            "overall_score",
        }

        self.assertEqual(
            set(sample.keys()),
            required,
        )


if __name__ == "__main__":
    unittest.main()