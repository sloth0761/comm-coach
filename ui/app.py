"""
ui/app.py

Main application window.
"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QMessageBox,
    QTextEdit,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QFrame,
)

from core.contracts import (
    Dimension,
)

from core.recorder import RecorderError

from ui.theme import score_colour
from ui.widgets import (
    PipelineWorker,
    PlaceholderWidget,
    ScoreCard,
    OverallScoreCard,
    MetricRow,
    TagLabel,
    CalloutBox,
    FocusBox,
)


IDLE = "idle"
RECORDING = "recording"
PROCESSING = "processing"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def trend_text(value: str) -> str:
    if value == "improving":
        return "↑ improving"

    if value == "declining":
        return "↓ declining"

    return "→ stable"


def trend_colour(value: str) -> str:
    if value == "improving":
        return "#4CAF50"

    if value == "declining":
        return "#F44336"

    return "#666666"


# ------------------------------------------------------------------
# Main Window
# ------------------------------------------------------------------


class MainWindow(QMainWindow):
    def __init__(
        self,
        pipeline,
        recorder,
        store,
    ):
        super().__init__()

        self.pipeline = pipeline
        self.recorder = recorder
        self.store = store

        self.worker = None
        self.current_result = None

        self.state = IDLE

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(
            self._update_elapsed_time
        )

        self.setWindowTitle("Comm Coach")
        self.setMinimumSize(900, 700)

        self._build_ui()

        self.refresh_session_count()
        self.refresh_history()

        if self.store.session_count() > 0:
            self.enable_result_tabs()

        else:
            self.disable_result_tabs()

        self.statusBar().showMessage("Ready")

    # ----------------------------------------------------------
    # UI Construction
    # ----------------------------------------------------------

    def _build_ui(self):

        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)

        root.addLayout(self._build_header())
        root.addLayout(self._build_record_area())

        self.tabs = QTabWidget()

        root.addWidget(self.tabs)

        self._build_overview_tab()
        self._build_fluency_tab()
        self._build_clarity_tab()
        self._build_expression_tab()
        self._build_ssc_tab()
        self._build_conciseness_tab()
        self._build_history_tab()
        self._build_profile_tab()

    # ----------------------------------------------------------
    # Header
    # ----------------------------------------------------------

    def _build_header(self):

        layout = QHBoxLayout()

        title = QLabel("Comm Coach")
        title.setObjectName("HeaderTitle")

        self.session_count_label = QLabel("0 sessions")

        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self.session_count_label)

        return layout

    # ----------------------------------------------------------
    # Record Area
    # ----------------------------------------------------------

    def _build_record_area(self):

        layout = QVBoxLayout()

        self.record_button = QPushButton("Record")
        self.record_button.setObjectName(
            "RecordButton"
        )

        self.record_button.clicked.connect(
            self.on_record_clicked
        )

        self.elapsed_label = QLabel("00:00")
        self.elapsed_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(
            self.record_button,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        layout.addWidget(
            self.elapsed_label,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        return layout

        # ----------------------------------------------------------
    # Overview Tab
    # ----------------------------------------------------------

    def _build_overview_tab(self):

        self.overview_tab = QWidget()
        self.tabs.addTab(
            self.overview_tab,
            "Overview",
        )

        layout = QVBoxLayout(self.overview_tab)

        self.overall_score_card = OverallScoreCard()
        layout.addWidget(self.overall_score_card)

        dimension_row = QHBoxLayout()

        self.dimension_cards = {}

        for dimension in Dimension:

            card = ScoreCard(
                dimension.value.replace("_", " ").title()
            )

            self.dimension_cards[dimension] = card

            dimension_row.addWidget(card)

        layout.addLayout(dimension_row)

        self.assessment_label = QLabel("")
        self.assessment_label.setWordWrap(True)

        layout.addWidget(self.assessment_label)

        self.key_insight_box = CalloutBox(
            "Key Insight"
        )

        layout.addWidget(self.key_insight_box)

        self.next_focus_box = FocusBox()

        layout.addWidget(self.next_focus_box)

        layout.addStretch()

    # ----------------------------------------------------------
    # Fluency Tab
    # ----------------------------------------------------------

    def _build_fluency_tab(self):

        self.fluency_tab = QWidget()

        self.tabs.addTab(
            self.fluency_tab,
            "Fluency",
        )

        layout = QVBoxLayout(self.fluency_tab)

        self.fluency_score = ScoreCard("Fluency")
        layout.addWidget(self.fluency_score)

        self.fluency_wpm = MetricRow(
            "Words per minute"
        )

        self.fluency_fillers = MetricRow(
            "Fillers per 100 words"
        )

        self.fluency_pauses = MetricRow(
            "Pause count"
        )

        layout.addWidget(self.fluency_wpm)

        note = QLabel(
            "Optimal: 120–160 WPM"
        )

        layout.addWidget(note)

        layout.addWidget(
            self.fluency_fillers
        )

        layout.addWidget(
            self.fluency_pauses
        )

        self.filler_tags_container = QWidget()
        self.filler_tags_layout = QHBoxLayout(
            self.filler_tags_container
        )

        layout.addWidget(
            self.filler_tags_container
        )

        self.fluency_feedback = QLabel("")
        self.fluency_feedback.setWordWrap(True)

        layout.addWidget(
            self.fluency_feedback
        )

        layout.addStretch()

    # ----------------------------------------------------------
    # Clarity Tab
    # ----------------------------------------------------------

    def _build_clarity_tab(self):

        self.clarity_tab = QWidget()

        self.tabs.addTab(
            self.clarity_tab,
            "Clarity",
        )

        layout = QVBoxLayout(self.clarity_tab)

        self.clarity_score = ScoreCard(
            "Clarity"
        )

        layout.addWidget(
            self.clarity_score
        )

        self.clarity_sentence_count = MetricRow(
            "Sentence count"
        )

        self.clarity_avg_sentence = MetricRow(
            "Average sentence length"
        )

        self.clarity_topic_drift = MetricRow(
            "Topic drift"
        )

        self.clarity_repetition = MetricRow(
            "Repeated phrase count"
        )

        layout.addWidget(
            self.clarity_sentence_count
        )

        layout.addWidget(
            self.clarity_avg_sentence
        )

        layout.addWidget(
            self.clarity_topic_drift
        )

        layout.addWidget(
            self.clarity_repetition
        )

        self.clarity_feedback = QLabel("")
        self.clarity_feedback.setWordWrap(True)

        layout.addWidget(
            self.clarity_feedback
        )

        layout.addStretch()

    # ----------------------------------------------------------
    # Expression Tab
    # ----------------------------------------------------------

    def _build_expression_tab(self):

        self.expression_tab = QWidget()

        self.tabs.addTab(
            self.expression_tab,
            "Expression",
        )

        layout = QVBoxLayout(
            self.expression_tab
        )

        self.expression_score = ScoreCard(
            "Expression"
        )

        layout.addWidget(
            self.expression_score
        )

        self.expression_ttr = MetricRow(
            "Vocabulary diversity"
        )

        self.expression_unique_words = MetricRow(
            "Unique content words"
        )

        self.expression_complex_ratio = MetricRow(
            "Complex word ratio"
        )

        self.expression_avg_length = MetricRow(
            "Average word length"
        )

        layout.addWidget(
            self.expression_ttr
        )

        layout.addWidget(
            self.expression_unique_words
        )

        layout.addWidget(
            self.expression_complex_ratio
        )

        layout.addWidget(
            self.expression_avg_length
        )

        self.expression_feedback = QLabel("")
        self.expression_feedback.setWordWrap(True)

        layout.addWidget(
            self.expression_feedback
        )

        layout.addStretch()

    # ----------------------------------------------------------
    # Speech Signal Clarity
    # ----------------------------------------------------------

    def _build_ssc_tab(self):

        self.ssc_tab = QWidget()

        self.tabs.addTab(
            self.ssc_tab,
            "Speech Signal Clarity",
        )

        layout = QVBoxLayout(
            self.ssc_tab
        )

        self.ssc_score = ScoreCard(
            "Speech Signal Clarity"
        )

        layout.addWidget(
            self.ssc_score
        )

        self.ssc_confidence = MetricRow(
            "Average confidence"
        )

        self.ssc_low_segments = MetricRow(
            "Low confidence segments"
        )

        layout.addWidget(
            self.ssc_confidence
        )

        layout.addWidget(
            self.ssc_low_segments
        )

        self.transcript_text = QTextEdit()
        self.transcript_text.setReadOnly(True)

        layout.addWidget(
            self.transcript_text
        )

        self.ssc_feedback = QLabel("")
        self.ssc_feedback.setWordWrap(True)

        layout.addWidget(
            self.ssc_feedback
        )

            # ----------------------------------------------------------
    # Conciseness Tab
    # ----------------------------------------------------------

    def _build_conciseness_tab(self):

        self.conciseness_tab = QWidget()

        self.tabs.addTab(
            self.conciseness_tab,
            "Conciseness",
        )

        layout = QVBoxLayout(
            self.conciseness_tab
        )

        self.conciseness_score = ScoreCard(
            "Conciseness"
        )

        layout.addWidget(
            self.conciseness_score
        )

        self.conciseness_verbose = MetricRow(
            "Verbose phrases found"
        )

        self.conciseness_repeated = MetricRow(
            "Repeated ideas"
        )

        self.conciseness_density = MetricRow(
            "Content word density"
        )

        layout.addWidget(
            self.conciseness_verbose
        )

        layout.addWidget(
            self.conciseness_repeated
        )

        layout.addWidget(
            self.conciseness_density
        )

        self.conciseness_feedback = QLabel("")
        self.conciseness_feedback.setWordWrap(True)

        layout.addWidget(
            self.conciseness_feedback
        )

        layout.addStretch()

    # ----------------------------------------------------------
    # History Tab
    # ----------------------------------------------------------

    def _build_history_tab(self):

        self.history_tab = QWidget()

        self.tabs.addTab(
            self.history_tab,
            "History",
        )

        layout = QVBoxLayout(
            self.history_tab
        )

        self.history_table = QTableWidget()

        self.history_table.setColumnCount(5)

        self.history_table.setHorizontalHeaderLabels(
            [
                "Date",
                "Duration",
                "Words",
                "WPM",
                "Score",
            ]
        )

        layout.addWidget(
            self.history_table
        )

        # v1.5: open detail view

    # ----------------------------------------------------------
    # Profile Tab
    # ----------------------------------------------------------

    def _build_profile_tab(self):

        self.profile_tab = QWidget()

        self.tabs.addTab(
            self.profile_tab,
            "Profile",
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        scroll.setWidget(container)

        self.tabs.removeTab(
            self.tabs.indexOf(self.profile_tab)
        )

        self.tabs.addTab(
            scroll,
            "Profile",
        )

        layout = QVBoxLayout(container)

        # Strengths

        strengths_title = QLabel(
            "Strengths"
        )
        strengths_title.setStyleSheet(
            "font-weight: bold;"
        )

        self.profile_strengths = QLabel("")
        self.profile_strengths.setWordWrap(True)

        layout.addWidget(
            strengths_title
        )

        layout.addWidget(
            self.profile_strengths
        )

        # Weaknesses

        weaknesses_title = QLabel(
            "Recurring weaknesses"
        )

        weaknesses_title.setStyleSheet(
            "font-weight: bold;"
        )

        self.profile_weaknesses = QLabel("")
        self.profile_weaknesses.setWordWrap(True)

        layout.addWidget(
            weaknesses_title
        )

        layout.addWidget(
            self.profile_weaknesses
        )

        # Trends

        trends_title = QLabel(
            "Trends"
        )

        trends_title.setStyleSheet(
            "font-weight: bold;"
        )

        layout.addWidget(
            trends_title
        )

        self.trends_container = QWidget()
        self.trends_layout = QVBoxLayout(
            self.trends_container
        )

        layout.addWidget(
            self.trends_container
        )

        # Fillers

        fillers_title = QLabel(
            "Persistent filler words"
        )

        fillers_title.setStyleSheet(
            "font-weight: bold;"
        )

        layout.addWidget(
            fillers_title
        )

        self.profile_fillers = QLabel("")
        self.profile_fillers.setWordWrap(True)

        layout.addWidget(
            self.profile_fillers
        )

        # Notable pattern

        pattern_title = QLabel(
            "Notable pattern"
        )

        pattern_title.setStyleSheet(
            "font-weight: bold;"
        )

        layout.addWidget(
            pattern_title
        )

        self.profile_pattern = QLabel("")
        self.profile_pattern.setWordWrap(True)

        layout.addWidget(
            self.profile_pattern
        )

        layout.addStretch()

    # ----------------------------------------------------------
    # Tab Helpers
    # ----------------------------------------------------------

    def disable_result_tabs(self):

        for i in range(self.tabs.count()):
            self.tabs.setTabEnabled(
                i,
                False,
            )

    def enable_result_tabs(self):

        for i in range(self.tabs.count()):
            self.tabs.setTabEnabled(
                i,
                True,
            )

    # ----------------------------------------------------------
    # Header Helpers
    # ----------------------------------------------------------

    def refresh_session_count(self):

        count = self.store.session_count()

        self.session_count_label.setText(
            f"{count} sessions"
        )

    # ----------------------------------------------------------
    # History Refresh
    # ----------------------------------------------------------

    def refresh_history(self):

        rows = self.store.all_sessions_summary()

        self.history_table.setRowCount(
            len(rows)
        )

        for row_idx, row in enumerate(rows):

            created = row["created_at"]

            if isinstance(
                created,
                datetime,
            ):
                created = created.strftime(
                    "%Y-%m-%d %H:%M"
                )

            values = [
                created,
                f'{row["duration_seconds"]:.1f}s',
                str(row["word_count"]),
                f'{row["speaking_rate_wpm"]:.0f}',
                f'{row["overall_score"]:.0f}',
            ]

            for col_idx, value in enumerate(values):

                self.history_table.setItem(
                    row_idx,
                    col_idx,
                    QTableWidgetItem(
                        str(value)
                    ),
                )

        self.history_table.resizeColumnsToContents()

            # ----------------------------------------------------------
    # Recording State Machine
    # ----------------------------------------------------------

    def on_record_clicked(self):

        if self.state == IDLE:
            self.start_recording()
            return

        if self.state == RECORDING:
            self.stop_recording()
            return

    def start_recording(self):

        try:
            self.recorder.start()

        except RecorderError as exc:

            QMessageBox.warning(
                self,
                "Microphone error",
                str(exc),
            )

            return

        self.state = RECORDING

        self.record_button.setText("Stop")

        self.record_button.setProperty(
            "recording",
            True,
        )

        self.record_button.setProperty(
            "processing",
            False,
        )

        self.record_button.style().unpolish(
            self.record_button
        )
        self.record_button.style().polish(
            self.record_button
        )

        self.elapsed_label.setText("00:00")

        self.timer.start()

        self.statusBar().showMessage(
            "Recording..."
        )

    def stop_recording(self):

        self.timer.stop()

        try:
            recording = self.recorder.stop()

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Recording error",
                str(exc),
            )

            self.set_idle_state()

            return

        self.start_pipeline(recording)

    # ----------------------------------------------------------
    # Processing State
    # ----------------------------------------------------------

    def start_pipeline(self, recording):

        self.state = PROCESSING

        self.record_button.setEnabled(False)

        self.record_button.setText(
            "Processing..."
        )

        self.record_button.setProperty(
            "recording",
            False,
        )

        self.record_button.setProperty(
            "processing",
            True,
        )

        self.record_button.style().unpolish(
            self.record_button
        )
        self.record_button.style().polish(
            self.record_button
        )

        self.statusBar().showMessage(
            "Starting pipeline..."
        )

        self.worker = PipelineWorker(
            self.pipeline,
            recording,
        )

        self.worker.stage_changed.connect(
            self.on_stage_changed
        )

        self.worker.finished_ok.connect(
            self.on_pipeline_finished
        )

        self.worker.failed.connect(
            self.on_pipeline_failed
        )

        self.worker.start()

    # ----------------------------------------------------------
    # Timer
    # ----------------------------------------------------------

    def _update_elapsed_time(self):

        seconds = int(
            self.recorder.elapsed_seconds
        )

        minutes = seconds // 60
        remaining = seconds % 60

        self.elapsed_label.setText(
            f"{minutes:02d}:{remaining:02d}"
        )

    # ----------------------------------------------------------
    # Pipeline Signals
    # ----------------------------------------------------------

    def on_stage_changed(self, stage_text):

        self.record_button.setText(
            f"{stage_text}..."
        )

        self.statusBar().showMessage(
            f"{stage_text}..."
        )

    def on_pipeline_failed(self, error):

        QMessageBox.critical(
            self,
            "Pipeline error",
            error,
        )

        self.set_idle_state()

    def on_pipeline_finished(
        self,
        session_result,
    ):

        self.current_result = session_result

        self.populate_from_result(
            session_result
        )

        self.refresh_session_count()
        self.refresh_history()

        self.enable_result_tabs()

        self.statusBar().showMessage(
            "Ready"
        )

        self.set_idle_state()

    # ----------------------------------------------------------
    # Return To Idle
    # ----------------------------------------------------------

    def set_idle_state(self):

        self.state = IDLE

        self.record_button.setEnabled(True)

        self.record_button.setText(
            "Record"
        )

        self.record_button.setProperty(
            "recording",
            False,
        )

        self.record_button.setProperty(
            "processing",
            False,
        )

        self.record_button.style().unpolish(
            self.record_button
        )
        self.record_button.style().polish(
            self.record_button
        )

        self.statusBar().showMessage(
            "Ready"
        )

            # ----------------------------------------------------------
    # Result Population
    # ----------------------------------------------------------

    def populate_from_result(
        self,
        result,
    ):

        self.populate_overview(result)
        self.populate_fluency(result)
        self.populate_clarity(result)
        self.populate_expression(result)
        self.populate_ssc(result)
        self.populate_conciseness(result)
        self.populate_profile(result)

    # ----------------------------------------------------------
    # Overview
    # ----------------------------------------------------------

    def populate_overview(self, result):

        self.overall_score_card.set_score(
            result.analytics.overall_score
        )

        for dimension_result in result.analytics.dimensions:

            card = self.dimension_cards[
                dimension_result.dimension
            ]

            card.set_score(
                dimension_result.score
            )

        self.assessment_label.setText(
            result.coaching.overall_assessment
        )

        self.key_insight_box.set_text(
            result.coaching.key_insight
        )

        self.next_focus_box.set_focus(
            result.coaching.next_focus
        )

    # ----------------------------------------------------------
    # Fluency
    # ----------------------------------------------------------

    def populate_fluency(self, result):

        fluency = result.analytics.dimensions[0]

        metrics = fluency.metrics

        self.fluency_score.set_score(
            fluency.score
        )

        self.fluency_wpm.set_value(
            f'{metrics["wpm"]:.0f}'
        )

        self.fluency_fillers.set_value(
            f'{metrics["filler_rate_per_100"]:.2f}'
        )

        self.fluency_pauses.set_value(
            str(metrics["pause_count"])
        )

        while self.filler_tags_layout.count():

            item = self.filler_tags_layout.takeAt(0)

            widget = item.widget()

            if widget:
                widget.deleteLater()

        for word, count in (
            fluency.filler_events.items()
        ):

            self.filler_tags_layout.addWidget(
                TagLabel(
                    f"{word} × {count}"
                )
            )

        self.filler_tags_layout.addStretch()

        self.fluency_feedback.setText(
            fluency.feedback
        )

    # ----------------------------------------------------------
    # Clarity
    # ----------------------------------------------------------

    def populate_clarity(self, result):

        clarity = result.analytics.dimensions[1]

        metrics = clarity.metrics

        self.clarity_score.set_score(
            clarity.score
        )

        self.clarity_sentence_count.set_value(
            str(
                metrics[
                    "sentence_count"
                ]
            )
        )

        self.clarity_avg_sentence.set_value(
            f'{metrics["avg_sentence_length"]:.1f}'
        )

        self.clarity_topic_drift.set_value(
            (
                "Detected"
                if metrics["topic_drift"]
                else "None"
            )
        )

        self.clarity_repetition.set_value(
            str(
                metrics[
                    "repeated_phrase_count"
                ]
            )
        )

        self.clarity_feedback.setText(
            clarity.feedback
        )

    # ----------------------------------------------------------
    # Expression
    # ----------------------------------------------------------

    def populate_expression(self, result):

        expression = (
            result.analytics.dimensions[2]
        )

        metrics = expression.metrics

        self.expression_score.set_score(
            expression.score
        )

        self.expression_ttr.set_value(
            f'{metrics["corrected_ttr"]:.1%}'
        )

        self.expression_unique_words.set_value(
            str(
                metrics[
                    "unique_content_words"
                ]
            )
        )

        self.expression_complex_ratio.set_value(
            f'{metrics["complex_word_ratio"]:.1%}'
        )

        self.expression_avg_length.set_value(
            f'{metrics["avg_content_word_length"]:.2f}'
        )

        self.expression_feedback.setText(
            expression.feedback
        )

    # ----------------------------------------------------------
    # Speech Signal Clarity
    # ----------------------------------------------------------

    def populate_ssc(self, result):

        ssc = result.analytics.dimensions[3]

        metrics = ssc.metrics

        self.ssc_score.set_score(
            ssc.score
        )

        self.ssc_confidence.set_value(
            f'{metrics["avg_confidence"]:.1%}'
        )

        self.ssc_low_segments.set_value(
            (
                f'{metrics["low_confidence_segments"]}'
                f' / {metrics["segment_count"]}'
            )
        )

        self.transcript_text.setPlainText(
            result.transcription.text
        )

        self.ssc_feedback.setText(
            ssc.feedback
        )

    # ----------------------------------------------------------
    # Conciseness
    # ----------------------------------------------------------

    def populate_conciseness(self, result):

        conciseness = (
            result.analytics.dimensions[4]
        )

        metrics = conciseness.metrics

        self.conciseness_score.set_score(
            conciseness.score
        )

        self.conciseness_verbose.set_value(
            str(
                metrics[
                    "verbose_phrase_count"
                ]
            )
        )

        self.conciseness_repeated.set_value(
            str(
                metrics[
                    "repeated_idea_count"
                ]
            )
        )

        self.conciseness_density.set_value(
            f'{metrics["content_word_density"]:.1%}'
        )

        self.conciseness_feedback.setText(
            conciseness.feedback
        )

    # ----------------------------------------------------------
    # Profile
    # ----------------------------------------------------------

    def populate_profile(self, result):

        profile = result.profile

        # Strengths

        if profile.strengths:

            self.profile_strengths.setText(
                "\n".join(
                    f"• {item}"
                    for item in profile.strengths
                )
            )

        else:

            self.profile_strengths.setText(
                (
                    "Complete more sessions "
                    "to identify strengths"
                )
            )

        # Weaknesses

        if profile.recurring_weaknesses:

            self.profile_weaknesses.setText(
                "\n".join(
                    f"• {item}"
                    for item in profile.recurring_weaknesses
                )
            )

        else:

            self.profile_weaknesses.setText(
                (
                    "No recurring patterns "
                    "detected yet"
                )
            )

        # Trends

        while self.trends_layout.count():

            item = self.trends_layout.takeAt(0)

            widget = item.widget()

            if widget:
                widget.deleteLater()

        for dimension, trend in (
            profile.trends.items()
        ):

            label = QLabel(
                f"{dimension} → "
                f"{trend_text(trend)}"
            )

            label.setStyleSheet(
                (
                    "font-weight: bold;"
                    f"color: {trend_colour(trend)};"
                )
            )

            self.trends_layout.addWidget(
                label
            )

        # Persistent Fillers

        if profile.persistent_fillers:

            lines = []

            for item in (
                profile.persistent_fillers
            ):

                lines.append(
                    (
                        f'{item["word"]}: '
                        f'{item["sessions_with"]} sessions, '
                        f'{item["total"]} total'
                    )
                )

            self.profile_fillers.setText(
                "\n".join(lines)
            )

        else:

            self.profile_fillers.setText(
                "No persistent filler words yet"
            )

        self.profile_pattern.setText(
            profile.notable_pattern
        )