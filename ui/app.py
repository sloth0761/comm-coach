"""
Main application window and pipeline worker thread.

Threading rule:
  Recording start/stop: UI thread (near-instant).
  Transcription onward: PipelineWorker (QThread).
  SQLite: check_same_thread=False; single writer, no locking needed in v1.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Callable

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QStatusBar,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from core.contracts import Dimension, SessionResult
from core.memory import MemoryStore
from core.recorder import AudioRecorder, RecorderError
from core.pipeline import SessionPipeline, PipelineStage
from ui.theme import STYLESHEET, score_color, score_bg
from ui.widgets import FillerTagRow, MetricRow, ScoreCard, SectionHeader


# ---------------------------------------------------------------------------
# Pipeline worker
# ---------------------------------------------------------------------------

class PipelineWorker(QThread):
    stage_changed = pyqtSignal(str)     # PipelineStage.value string
    finished_ok   = pyqtSignal(object)  # SessionResult
    failed        = pyqtSignal(str)     # error message

    def __init__(self, pipeline: SessionPipeline, recording) -> None:
        super().__init__()
        self._pipeline  = pipeline
        self._recording = recording

    def run(self) -> None:
        self._pipeline._on_stage = lambda s: self.stage_changed.emit(s.value)
        try:
            result = self._pipeline.run(self._recording)
            self.finished_ok.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


# ---------------------------------------------------------------------------
# Record button state
# ---------------------------------------------------------------------------

class _State(enum.Enum):
    IDLE       = "idle"
    RECORDING  = "recording"
    PROCESSING = "processing"


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):

    def __init__(
        self,
        pipeline: SessionPipeline,
        recorder: AudioRecorder,
        store: MemoryStore,
    ) -> None:
        super().__init__()
        self._pipeline = pipeline
        self._recorder = recorder
        self._store    = store
        self._worker:  PipelineWorker | None = None
        self._state    = _State.IDLE
        self._metrics: dict[str, dict[str, MetricRow]] = {}

        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)

        self._setup_ui()
        self._update_session_count()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setWindowTitle("Comm Coach")
        self.setMinimumSize(960, 720)
        self.setStyleSheet(STYLESHEET)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_record_area())
        root.addWidget(self._build_tabs(), 1)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setObjectName("header")
        row = QHBoxLayout(w)
        row.setContentsMargins(20, 12, 20, 12)

        self._app_title = QLabel("Comm Coach")
        self._app_title.setObjectName("app_title")

        self._session_count_label = QLabel("")
        self._session_count_label.setObjectName("session_count")

        row.addWidget(self._app_title)
        row.addStretch()
        row.addWidget(self._session_count_label)
        return w

    def _build_record_area(self) -> QWidget:
        w = QWidget()
        w.setObjectName("record_area")
        w.setFixedHeight(180)
        row = QHBoxLayout(w)
        row.setContentsMargins(40, 20, 40, 20)
        row.setSpacing(40)

        self._record_btn = QPushButton("Record")
        self._record_btn.setObjectName("record_button")
        self._record_btn.setFixedSize(120, 120)
        self._record_btn.clicked.connect(self._on_record_clicked)

        info_col = QVBoxLayout()
        info_col.setSpacing(8)

        self._elapsed_label = QLabel("0:00")
        self._elapsed_label.setObjectName("elapsed_label")

        self._stage_label = QLabel("Press Record to begin")
        self._stage_label.setObjectName("stage_label")

        info_col.addStretch()
        info_col.addWidget(self._elapsed_label)
        info_col.addWidget(self._stage_label)
        info_col.addStretch()

        row.addWidget(self._record_btn)
        row.addLayout(info_col)
        row.addStretch()
        return w

    def _build_tabs(self) -> QTabWidget:
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_overview_tab(),    "Overview")
        self._tabs.addTab(self._build_fluency_tab(),     "Fluency")
        self._tabs.addTab(self._build_clarity_tab(),     "Clarity")
        self._tabs.addTab(self._build_expression_tab(),  "Expression")
        self._tabs.addTab(self._build_ssc_tab(),         "Signal Clarity")
        self._tabs.addTab(self._build_conciseness_tab(), "Conciseness")
        self._tabs.addTab(self._build_history_tab(),     "History")
        self._tabs.addTab(self._build_profile_tab(),     "Profile")
        return self._tabs

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------

    def _scrollable(self, inner: QWidget) -> QScrollArea:
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setWidget(inner)
        return sa

    def _padded(self) -> tuple[QWidget, QVBoxLayout]:
        """Return (container_widget, vbox_layout) with standard padding."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        return w, lay

    def _build_overview_tab(self) -> QScrollArea:
        w, lay = self._padded()

        # Overall score
        score_row = QHBoxLayout()
        self._overall_score_label = QLabel("—")
        self._overall_score_label.setStyleSheet(
            "font-size: 72px; font-weight: bold; color: #9E9E9E;"
        )
        of_label = QLabel(" / 100")
        of_label.setStyleSheet("font-size: 24px; color: #9E9E9E; padding-top: 32px;")
        score_row.addWidget(self._overall_score_label)
        score_row.addWidget(of_label)
        score_row.addStretch()
        lay.addLayout(score_row)

        # 5 dimension score cards
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        self._score_cards: dict[Dimension, ScoreCard] = {}
        titles = {
            Dimension.FLUENCY:               "Fluency",
            Dimension.CLARITY:               "Clarity",
            Dimension.EXPRESSION:            "Expression",
            Dimension.SPEECH_SIGNAL_CLARITY: "Signal\nClarity",
            Dimension.CONCISENESS:           "Conciseness",
        }
        for dim, title in titles.items():
            card = ScoreCard(title)
            self._score_cards[dim] = card
            cards_row.addWidget(card)
        lay.addLayout(cards_row)

        lay.addWidget(SectionHeader("Assessment"))
        self._assessment_label = QLabel("Complete a recording to see your assessment.")
        self._assessment_label.setWordWrap(True)
        self._assessment_label.setObjectName("placeholder")
        lay.addWidget(self._assessment_label)

        lay.addWidget(SectionHeader("Key Insight"))
        self._key_insight_box = QLabel("—")
        self._key_insight_box.setObjectName("key_insight_box")
        self._key_insight_box.setWordWrap(True)
        lay.addWidget(self._key_insight_box)

        lay.addWidget(SectionHeader("Next Focus"))
        self._next_focus_box = QLabel("—")
        self._next_focus_box.setObjectName("next_focus_box")
        self._next_focus_box.setWordWrap(True)
        lay.addWidget(self._next_focus_box)

        lay.addStretch()
        return self._scrollable(w)

    def _build_dim_tab(self, dim_key: str, metric_defs: list[tuple[str, str]]) -> QScrollArea:
        """
        Generic dimension tab builder.
        metric_defs: list of (metric_dict_key, display_label) pairs.
        Returns a QScrollArea. Stores a ScoreCard and MetricRow references.
        """
        w, lay = self._padded()

        card = ScoreCard(dim_key.replace("_", " ").title())
        lay.addWidget(card)
        # Store card so populate can find it
        setattr(self, f"_dim_card_{dim_key}", card)

        lay.addWidget(SectionHeader("Metrics"))
        rows: dict[str, MetricRow] = {}
        for key, label in metric_defs:
            row = MetricRow(label)
            rows[key] = row
            lay.addWidget(row)
        self._metrics[dim_key] = rows

        lay.addWidget(SectionHeader("Feedback"))
        feedback = QLabel("—")
        feedback.setWordWrap(True)
        setattr(self, f"_feedback_{dim_key}", feedback)
        lay.addWidget(feedback)

        lay.addStretch()
        return self._scrollable(w)

    def _build_fluency_tab(self) -> QScrollArea:
        w, lay = self._padded()

        self._dim_card_fluency = ScoreCard("Fluency")
        lay.addWidget(self._dim_card_fluency)

        lay.addWidget(SectionHeader("Pace"))
        rows: dict[str, MetricRow] = {}
        for key, label in [("wpm", "Words per minute"), ("pause_count", "Pauses (> 0.5 s)")]:
            r = MetricRow(label)
            rows[key] = r
            lay.addWidget(r)

        lay.addWidget(SectionHeader("Filler Words"))
        for key, label in [("filler_count", "Total fillers"), ("filler_rate_per_100", "Per 100 words")]:
            r = MetricRow(label)
            rows[key] = r
            lay.addWidget(r)
        self._metrics["fluency"] = rows

        self._filler_tag_row = FillerTagRow()
        lay.addWidget(self._filler_tag_row)

        lay.addWidget(SectionHeader("Feedback"))
        self._feedback_fluency = QLabel("—")
        self._feedback_fluency.setWordWrap(True)
        lay.addWidget(self._feedback_fluency)
        lay.addStretch()
        return self._scrollable(w)

    def _build_clarity_tab(self) -> QScrollArea:
        return self._build_dim_tab("clarity", [
            ("sentence_count",        "Sentences"),
            ("avg_sentence_length",   "Avg sentence length (words)"),
            ("repeated_phrase_count", "Repeated phrases"),
            ("topic_drift",           "Topic drift"),
        ])

    def _build_expression_tab(self) -> QScrollArea:
        return self._build_dim_tab("expression", [
            ("corrected_ttr",          "Vocabulary diversity (TTR)"),
            ("unique_content_words",   "Unique content words"),
            ("complex_word_ratio",     "Complex word ratio (> 7 chars)"),
            ("avg_content_word_length","Avg content word length"),
        ])

    def _build_ssc_tab(self) -> QScrollArea:
        w, lay = self._padded()

        self._dim_card_speech_signal_clarity = ScoreCard("Signal Clarity")
        lay.addWidget(self._dim_card_speech_signal_clarity)

        lay.addWidget(SectionHeader("Confidence Metrics"))
        rows: dict[str, MetricRow] = {}
        for key, label in [
            ("avg_confidence",          "Avg segment confidence"),
            ("low_confidence_segments", "Low-confidence segments"),
            ("segment_count",           "Total segments"),
        ]:
            r = MetricRow(label)
            rows[key] = r
            lay.addWidget(r)
        self._metrics["speech_signal_clarity"] = rows

        lay.addWidget(SectionHeader("Full Transcript"))
        self._transcript_label = QLabel("—")
        self._transcript_label.setWordWrap(True)
        self._transcript_label.setStyleSheet(
            "background-color: #FFFFFF; border: 1px solid #E0E0E0; "
            "border-radius: 4px; padding: 12px; line-height: 1.6;"
        )
        lay.addWidget(self._transcript_label)

        lay.addWidget(SectionHeader("Feedback"))
        self._feedback_speech_signal_clarity = QLabel("—")
        self._feedback_speech_signal_clarity.setWordWrap(True)
        lay.addWidget(self._feedback_speech_signal_clarity)
        lay.addStretch()
        return self._scrollable(w)

    def _build_conciseness_tab(self) -> QScrollArea:
        return self._build_dim_tab("conciseness", [
            ("verbose_phrase_count", "Verbose phrases"),
            ("repeated_idea_count",  "Repeated ideas"),
            ("content_word_density", "Content word density"),
        ])

    def _build_history_tab(self) -> QWidget:
        w, lay = self._padded()

        lay.addWidget(SectionHeader("Past Sessions"))
        self._history_table = QTableWidget(0, 5)
        self._history_table.setHorizontalHeaderLabels(["Date", "Duration", "Words", "WPM", "Score"])
        self._history_table.horizontalHeader().setStretchLastSection(True)
        self._history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._history_table.verticalHeader().setVisible(False)
        lay.addWidget(self._history_table, 1)
        return w

    def _build_profile_tab(self) -> QScrollArea:
        w, lay = self._padded()

        lay.addWidget(SectionHeader("Strengths"))
        self._profile_strengths = QLabel("Complete more sessions to identify strengths.")
        self._profile_strengths.setWordWrap(True)
        self._profile_strengths.setObjectName("placeholder")
        lay.addWidget(self._profile_strengths)

        lay.addWidget(SectionHeader("Recurring Weaknesses"))
        self._profile_weaknesses = QLabel("No recurring patterns detected yet.")
        self._profile_weaknesses.setWordWrap(True)
        self._profile_weaknesses.setObjectName("placeholder")
        lay.addWidget(self._profile_weaknesses)

        lay.addWidget(SectionHeader("Trends"))
        self._profile_trends_widget = QWidget()
        self._profile_trends_layout = QVBoxLayout(self._profile_trends_widget)
        self._profile_trends_layout.setContentsMargins(0, 0, 0, 0)
        self._profile_trends_layout.setSpacing(4)
        lay.addWidget(self._profile_trends_widget)

        lay.addWidget(SectionHeader("Persistent Filler Words"))
        self._profile_fillers = QLabel("No persistent filler words yet.")
        self._profile_fillers.setWordWrap(True)
        self._profile_fillers.setObjectName("placeholder")
        lay.addWidget(self._profile_fillers)

        lay.addWidget(SectionHeader("Notable Pattern"))
        self._profile_notable = QLabel("—")
        self._profile_notable.setWordWrap(True)
        lay.addWidget(self._profile_notable)

        lay.addStretch()
        return self._scrollable(w)

    # ------------------------------------------------------------------
    # Record button logic
    # ------------------------------------------------------------------

    def _on_record_clicked(self) -> None:
        if self._state == _State.IDLE:
            self._start_recording()
        elif self._state == _State.RECORDING:
            self._stop_recording()

    def _start_recording(self) -> None:
        try:
            self._recorder.start()
        except RecorderError as exc:
            QMessageBox.warning(self, "Microphone Error", str(exc))
            return
        self._set_state(_State.RECORDING)
        self._elapsed_timer.start()

    def _stop_recording(self) -> None:
        self._elapsed_timer.stop()
        recording = self._recorder.stop()
        self._set_state(_State.PROCESSING)
        self._stage_label.setText("Transcribing…")

        self._worker = PipelineWorker(self._pipeline, recording)
        self._worker.stage_changed.connect(self._on_stage_changed)
        self._worker.finished_ok.connect(self._on_pipeline_done)
        self._worker.failed.connect(self._on_pipeline_failed)
        self._worker.start()

    def _set_state(self, state: _State) -> None:
        self._state = state
        self._record_btn.setProperty("state", state.value)
        # Force QSS re-evaluation
        self._record_btn.style().unpolish(self._record_btn)
        self._record_btn.style().polish(self._record_btn)

        if state == _State.IDLE:
            self._record_btn.setText("Record")
            self._record_btn.setEnabled(True)
            self._stage_label.setText("Press Record to begin")
            self._elapsed_label.setText("0:00")
            self.statusBar().showMessage("Ready")
        elif state == _State.RECORDING:
            self._record_btn.setText("Stop")
            self._record_btn.setEnabled(True)
            self.statusBar().showMessage("Recording…")
        elif state == _State.PROCESSING:
            self._record_btn.setText("Processing")
            self._record_btn.setEnabled(False)

    def _tick_elapsed(self) -> None:
        secs = int(self._recorder.elapsed_seconds)
        self._elapsed_label.setText(f"{secs // 60}:{secs % 60:02d}")

    # ------------------------------------------------------------------
    # Pipeline callbacks
    # ------------------------------------------------------------------

    def _on_stage_changed(self, stage_value: str) -> None:
        self._stage_label.setText(f"{stage_value}…")
        self.statusBar().showMessage(stage_value)

    def _on_pipeline_done(self, result: SessionResult) -> None:
        self._populate_all_tabs(result)
        self._update_session_count()
        self._set_state(_State.IDLE)
        self.statusBar().showMessage(
            f"Session {result.session_id} complete — overall score: {result.analytics.overall_score:.0f}"
        )

    def _on_pipeline_failed(self, error: str) -> None:
        self._set_state(_State.IDLE)
        QMessageBox.critical(self, "Pipeline Error", error)
        self.statusBar().showMessage("Error — see message above")

    # ------------------------------------------------------------------
    # Tab population
    # ------------------------------------------------------------------

    def _populate_all_tabs(self, r: SessionResult) -> None:
        self._populate_overview(r)
        self._populate_fluency(r)
        self._populate_dim("clarity",               r)
        self._populate_dim("expression",            r)
        self._populate_ssc(r)
        self._populate_dim("conciseness",           r)
        self._populate_history()
        self._populate_profile(r)

    def _populate_overview(self, r: SessionResult) -> None:
        score = r.analytics.overall_score
        self._overall_score_label.setText(f"{score:.0f}")
        self._overall_score_label.setStyleSheet(
            f"font-size: 72px; font-weight: bold; color: {score_color(score)};"
        )
        for dim_result in r.analytics.dimensions:
            self._score_cards[dim_result.dimension].set_score(dim_result.score)

        self._assessment_label.setText(r.coaching.overall_assessment)
        self._assessment_label.setObjectName("")           # remove placeholder italic
        self._key_insight_box.setText("💡  " + r.coaching.key_insight)
        self._next_focus_box.setText("🎯  " + r.coaching.next_focus)

    def _populate_fluency(self, r: SessionResult) -> None:
        dim = next(d for d in r.analytics.dimensions if d.dimension == Dimension.FLUENCY)
        self._dim_card_fluency.set_score(dim.score)
        m = dim.metrics
        rows = self._metrics["fluency"]
        rows["wpm"].set_value(f"{m.get('wpm', 0):.0f} WPM")
        rows["pause_count"].set_value(str(m.get("pause_count", 0)))
        rows["filler_count"].set_value(str(m.get("filler_count", 0)))
        rows["filler_rate_per_100"].set_value(f"{m.get('filler_rate_per_100', 0):.1f}")
        self._filler_tag_row.set_fillers(dim.filler_events)
        self._feedback_fluency.setText(dim.feedback)

    def _populate_dim(self, dim_key: str, r: SessionResult) -> None:
        """Generic populate for clarity, expression, conciseness."""
        dim_enum = Dimension(dim_key)
        dim = next(d for d in r.analytics.dimensions if d.dimension == dim_enum)
        card: ScoreCard = getattr(self, f"_dim_card_{dim_key}")
        card.set_score(dim.score)

        m = dim.metrics
        for key, row in self._metrics[dim_key].items():
            raw = m.get(key)
            if raw is None:
                row.set_value("—")
            elif isinstance(raw, bool):
                row.set_value("Detected" if raw else "None",
                              color="#C62828" if raw else "#2E7D32")
            elif isinstance(raw, float):
                # If it looks like a ratio (0–1 range), show as percentage
                if 0 <= raw <= 1.0 and key not in ("avg_sentence_length", "avg_content_word_length"):
                    row.set_value(f"{raw * 100:.1f}%")
                else:
                    row.set_value(f"{raw:.1f}")
            else:
                row.set_value(str(raw))

        feedback_label: QLabel = getattr(self, f"_feedback_{dim_key}")
        feedback_label.setText(dim.feedback)

    def _populate_ssc(self, r: SessionResult) -> None:
        dim = next(d for d in r.analytics.dimensions
                   if d.dimension == Dimension.SPEECH_SIGNAL_CLARITY)
        self._dim_card_speech_signal_clarity.set_score(dim.score)
        m = dim.metrics
        rows = self._metrics["speech_signal_clarity"]
        rows["avg_confidence"].set_value(f"{m.get('avg_confidence', 0) * 100:.1f}%")
        rows["low_confidence_segments"].set_value(
            f"{m.get('low_confidence_segments', 0)} of {m.get('segment_count', 0)}"
        )
        rows["segment_count"].set_value(str(m.get("segment_count", 0)))
        self._transcript_label.setText(r.transcription.text)
        self._feedback_speech_signal_clarity.setText(dim.feedback)

    def _populate_history(self) -> None:
        sessions = self._store.all_sessions_summary()
        self._history_table.setRowCount(len(sessions))
        for row_idx, s in enumerate(sessions):
            created = str(s.get("created_at", ""))[:16].replace("T", " ")
            dur_s   = s.get("duration_seconds", 0)
            dur_str = f"{int(dur_s) // 60}:{int(dur_s) % 60:02d}"
            wpm     = s.get("speaking_rate_wpm", 0)
            sc      = s.get("overall_score", 0)

            score_item = QTableWidgetItem(f"{sc:.0f}")
            score_item.setForeground(
                __import__("PyQt6.QtGui", fromlist=["QColor"]).QColor(score_color(sc))
            )

            self._history_table.setItem(row_idx, 0, QTableWidgetItem(created))
            self._history_table.setItem(row_idx, 1, QTableWidgetItem(dur_str))
            self._history_table.setItem(row_idx, 2, QTableWidgetItem(str(s.get("word_count", 0))))
            self._history_table.setItem(row_idx, 3, QTableWidgetItem(f"{wpm:.0f}"))
            self._history_table.setItem(row_idx, 4, score_item)

        self._history_table.resizeColumnsToContents()

    def _populate_profile(self, r: SessionResult) -> None:
        p = r.profile

        # Strengths
        if p.strengths:
            self._profile_strengths.setText("\n".join(f"• {s}" for s in p.strengths))
            self._profile_strengths.setObjectName("")
        else:
            self._profile_strengths.setText("Complete more sessions to identify strengths.")

        # Weaknesses
        if p.recurring_weaknesses:
            self._profile_weaknesses.setText("\n".join(f"• {w}" for w in p.recurring_weaknesses))
            self._profile_weaknesses.setObjectName("")
        else:
            self._profile_weaknesses.setText("No recurring patterns detected yet.")

        # Trends — clear and rebuild
        while self._profile_trends_layout.count():
            item = self._profile_trends_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        arrows = {"improving": ("↑", "#2E7D32"), "declining": ("↓", "#C62828"),
                  "stable": ("→", "#757575")}
        for dim_str, direction in p.trends.items():
            arrow, colour = arrows.get(direction, ("→", "#757575"))
            label = QLabel(
                f'<span style="color:{colour};font-weight:bold">{arrow}</span> '
                f'{dim_str.replace("_", " ").title()} — {direction}'
            )
            label.setTextFormat(Qt.TextFormat.RichText)
            self._profile_trends_layout.addWidget(label)

        # Persistent fillers
        if p.persistent_fillers:
            lines = [
                f'• "{f["word"]}" — {f["sessions_with"]} sessions, {f["total"]} total'
                for f in p.persistent_fillers
            ]
            self._profile_fillers.setText("\n".join(lines))
            self._profile_fillers.setObjectName("")
        else:
            self._profile_fillers.setText("No persistent filler words yet.")

        # Notable pattern
        self._profile_notable.setText(p.notable_pattern)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _update_session_count(self) -> None:
        n = self._store.session_count()
        self._session_count_label.setText(
            f"{n} session{'s' if n != 1 else ''}" if n else ""
        )