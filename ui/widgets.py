"""
ui/widgets.py

Reusable widgets used by the Comm Coach UI.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
)

from ui.theme import score_colour


# ------------------------------------------------------------------
# Pipeline Worker
# ------------------------------------------------------------------


class PipelineWorker(QThread):
    """
    Runs SessionPipeline in a background thread.

    Emits:
        stage_changed(str)
        finished_ok(SessionResult)
        failed(str)
    """

    stage_changed = pyqtSignal(str)
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, pipeline, recording):
        super().__init__()

        self._pipeline = pipeline
        self._recording = recording

    def run(self) -> None:
        self._pipeline._on_stage = (
            lambda stage: self.stage_changed.emit(stage.value)
        )

        try:
            result = self._pipeline.run(self._recording)
            self.finished_ok.emit(result)

        except Exception as exc:
            self.failed.emit(str(exc))


# ------------------------------------------------------------------
# Placeholder Widget
# ------------------------------------------------------------------


class PlaceholderWidget(QWidget):
    """
    Displayed until the user completes
    their first recording.
    """

    def __init__(
        self,
        text: str = "Complete a recording to see results.",
    ):
        super().__init__()

        layout = QVBoxLayout(self)

        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)

        layout.addStretch()
        layout.addWidget(label)
        layout.addStretch()


# ------------------------------------------------------------------
# Tag Label
# ------------------------------------------------------------------


class TagLabel(QLabel):
    """
    Example:
        [um × 8]
        [basically × 3]
    """

    def __init__(self, text: str):
        super().__init__(text)

        self.setObjectName("TagLabel")

        self.setStyleSheet(
            """
            QLabel {
                background: #E9EEF8;
                border-radius: 10px;
                padding: 4px 10px;
            }
            """
        )


# ------------------------------------------------------------------
# Metric Row
# ------------------------------------------------------------------


class MetricRow(QWidget):
    """
    Reusable label/value row.

    Example:

        Words per minute     142
        Fillers / 100 words  3.4
    """

    def __init__(self, label: str, value: str = ""):
        super().__init__()

        layout = QHBoxLayout(self)

        self.label_widget = QLabel(label)
        self.value_widget = QLabel(value)

        self.value_widget.setAlignment(
            Qt.AlignmentFlag.AlignRight
        )

        self.value_widget.setStyleSheet(
            "font-weight: bold;"
        )

        layout.addWidget(self.label_widget)
        layout.addStretch()
        layout.addWidget(self.value_widget)

    def set_value(self, value: str) -> None:
        self.value_widget.setText(value)


# ------------------------------------------------------------------
# Score Card
# ------------------------------------------------------------------


class ScoreCard(QFrame):
    """
    Generic score card used throughout the app.
    """

    def __init__(
        self,
        title: str = "",
        score: Optional[float] = None,
    ):
        super().__init__()

        self.setObjectName("ScoreCard")

        self.setFrameShape(QFrame.Shape.StyledPanel)

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        layout = QVBoxLayout(self)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("ScoreTitle")

        self.score_label = QLabel("--")
        self.score_label.setObjectName("DimensionScore")
        self.score_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(
            self.title_label,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        layout.addWidget(
            self.score_label,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        if score is not None:
            self.set_score(score)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def set_score(self, score: float) -> None:
        self.score_label.setText(f"{score:.0f}")

        colour = score_colour(score)

        self.score_label.setStyleSheet(
            f"""
            color: {colour};
            font-size: 26px;
            font-weight: bold;
            """
        )


# ------------------------------------------------------------------
# Large Overview Score Card
# ------------------------------------------------------------------


class OverallScoreCard(QFrame):
    """
    Large overview score shown on Overview tab.
    """

    def __init__(self):
        super().__init__()

        self.setObjectName("ScoreCard")

        layout = QVBoxLayout(self)

        title = QLabel("Overall Score")
        title.setObjectName("ScoreTitle")

        self.score_label = QLabel("--")
        self.score_label.setObjectName("OverallScore")

        self.score_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(
            title,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        layout.addWidget(
            self.score_label,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

    def set_score(self, score: float) -> None:
        colour = score_colour(score)

        self.score_label.setText(
            f"{score:.0f}/100"
        )

        self.score_label.setStyleSheet(
            f"""
            color: {colour};
            font-size: 42px;
            font-weight: bold;
            """
        )


# ------------------------------------------------------------------
# Callout Box
# ------------------------------------------------------------------


class CalloutBox(QFrame):
    """
    Key Insight panel.
    """

    def __init__(self, title: str):
        super().__init__()

        self.setObjectName("CalloutBox")

        layout = QVBoxLayout(self)

        self.title_label = QLabel(title)

        self.body_label = QLabel("")
        self.body_label.setWordWrap(True)

        self.title_label.setStyleSheet(
            "font-weight: bold;"
        )

        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)

    def set_text(self, text: str) -> None:
        self.body_label.setText(text)


# ------------------------------------------------------------------
# Focus Box
# ------------------------------------------------------------------


class FocusBox(QFrame):
    """
    Next practice focus panel.
    """

    def __init__(self):
        super().__init__()

        self.setObjectName("FocusBox")

        layout = QVBoxLayout(self)

        self.label = QLabel("")
        self.label.setWordWrap(True)

        layout.addWidget(self.label)

    def set_focus(self, text: str) -> None:
        self.label.setText(f"🎯 {text}")