"""
Reusable UI components used across multiple tabs.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from ui.theme import score_color, score_bg


class ScoreCard(QFrame):
    """
    Compact card showing a dimension name and its 0–100 score.
    Background and score colour change based on the score value.
    """

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("score_card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        self._title_label = QLabel(title)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setStyleSheet("font-size: 12px; color: #757575; font-weight: bold;")
        self._title_label.setWordWrap(True)

        self._score_label = QLabel("—")
        self._score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._score_label.setStyleSheet("font-size: 28px; font-weight: bold;")

        layout.addWidget(self._title_label)
        layout.addWidget(self._score_label)

    def set_score(self, score: float) -> None:
        self._score_label.setText(f"{score:.0f}")
        self._score_label.setStyleSheet(
            f"font-size: 28px; font-weight: bold; color: {score_color(score)};"
        )
        self.setStyleSheet(
            f"#score_card {{ background-color: {score_bg(score)}; "
            f"border: 1px solid #E0E0E0; border-radius: 8px; }}"
        )

    def reset(self) -> None:
        self._score_label.setText("—")
        self._score_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #757575;")
        self.setStyleSheet(
            "#score_card { background-color: #FFFFFF; border: 1px solid #E0E0E0; border-radius: 8px; }"
        )


class MetricRow(QWidget):
    """A label + value pair for displaying a single metric."""

    def __init__(
        self,
        label: str,
        value: str = "—",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        name = QLabel(label)
        name.setStyleSheet("color: #757575; min-width: 200px;")

        self._value_label = QLabel(value)
        self._value_label.setStyleSheet("font-weight: bold;")

        layout.addWidget(name)
        layout.addWidget(self._value_label, 1)

    def set_value(self, value: str, color: str | None = None) -> None:
        self._value_label.setText(value)
        style = "font-weight: bold;"
        if color:
            style += f" color: {color};"
        self._value_label.setStyleSheet(style)

    @property
    def value_label(self) -> QLabel:
        return self._value_label


class SectionHeader(QLabel):
    """Small all-caps section header used in tabs and the profile."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text.upper(), parent)
        self.setObjectName("section_header")


class FillerTagRow(QWidget):
    """A horizontal row of coloured pill tags, one per filler word."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._layout.addStretch()

    def set_fillers(self, filler_events: dict[str, int]) -> None:
        # Clear existing tags
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for word, count in sorted(filler_events.items(), key=lambda x: -x[1]):
            tag = QLabel(f'{word}  ×{count}')
            tag.setObjectName("filler_tag")
            self._layout.insertWidget(self._layout.count() - 1, tag)