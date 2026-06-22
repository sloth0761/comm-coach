"""
ui/app.py

Main application window (v1.5).
"""
from __future__ import annotations

import logging
from datetime import datetime

from PyQt6.QtCore import QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QListWidget,
    QMainWindow, QPushButton, QSizePolicy, QStackedWidget, QStatusBar,
    QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget,
)

from core.contracts import Dimension, SessionResult
from ui.charts import TrendDashboard, score_colour
from ui.transcript_view import TranscriptView

logger = logging.getLogger(__name__)


class PipelineWorker(QThread):
    stage_changed = pyqtSignal(str)
    finished_ok   = pyqtSignal(object)
    failed        = pyqtSignal(str)

    def __init__(self, pipeline, recording):
        super().__init__()
        self._pipeline  = pipeline
        self._recording = recording

    def run(self):
        self._pipeline.set_on_stage(lambda s: self.stage_changed.emit(s.value))
        try:
            self.finished_ok.emit(self._pipeline.run(self._recording))
        except Exception as exc:
            logger.exception("Pipeline error")
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, pipeline, store):
        super().__init__()
        self._dim_widgets: dict = {}
        self._pipeline = pipeline
        self._store    = store
        self._recorder = None
        self._worker   = None
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)
        self.setWindowTitle("Comm Coach")
        self.setMinimumSize(960, 700)
        self._setup_ui()
        self.refresh_history()

    # ── UI setup ──────────────────────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._build_header())
        root.addWidget(self._build_record_bar())
        root.addWidget(self._build_tabs(), stretch=1)
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

    def _build_header(self):
        w = QWidget()
        w.setObjectName("Header")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(16, 8, 16, 8)
        title = QLabel("Comm Coach")
        title.setStyleSheet("color:white;font-size:18px;font-weight:700;")
        lay.addWidget(title)
        lay.addStretch()
        self._session_count_label = QLabel(self._session_count_text())
        self._session_count_label.setStyleSheet("color:rgba(255,255,255,0.8);font-size:12px;")
        lay.addWidget(self._session_count_label)
        return w

    def _build_record_bar(self):
        w = QWidget()
        w.setObjectName("RecordBar")
        outer = QVBoxLayout(w)
        outer.setContentsMargins(24, 14, 24, 14)
        self._record_stack = QStackedWidget()
        self._record_stack.setFixedHeight(64)

        # page 0 — idle
        idle = QWidget()
        il = QHBoxLayout(idle)
        il.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._start_btn = QPushButton("● Start Recording")
        self._start_btn.setObjectName("RecordButton")
        self._start_btn.clicked.connect(self.start_recording)
        il.addWidget(self._start_btn)
        self._record_stack.addWidget(idle)

        # page 1 — recording
        rec = QWidget()
        rl = QHBoxLayout(rec)
        rl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rl.setSpacing(20)
        self._elapsed_label = QLabel("0:00")
        self._elapsed_label.setStyleSheet("font-size:22px;font-weight:700;color:#C62828;")
        self._stop_btn = QPushButton("■ Stop Recording")
        self._stop_btn.setObjectName("RecordButton")
        self._stop_btn.clicked.connect(self.stop_recording)
        rl.addWidget(self._elapsed_label)
        rl.addWidget(self._stop_btn)
        self._record_stack.addWidget(rec)

        # page 2 — processing
        proc = QWidget()
        pl = QHBoxLayout(proc)
        pl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._proc_label = QLabel("Processing…")
        self._proc_label.setStyleSheet("font-size:14px;color:#546E7A;")
        pl.addWidget(self._proc_label)
        self._record_stack.addWidget(proc)

        outer.addWidget(self._record_stack)
        return w

    def _build_tabs(self):
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.addTab(self._build_overview_tab(),                         "Overview")
        self._tabs.addTab(self._build_dim_tab(Dimension.FLUENCY),             "Fluency")
        self._tabs.addTab(self._build_dim_tab(Dimension.CLARITY),             "Clarity")
        self._tabs.addTab(self._build_dim_tab(Dimension.EXPRESSION),          "Expression")
        self._tabs.addTab(self._build_dim_tab(Dimension.SPEECH_SIGNAL_CLARITY),"Signal Clarity")
        self._tabs.addTab(self._build_dim_tab(Dimension.CONCISENESS),         "Conciseness")
        self._tabs.addTab(self._build_transcript_tab(),                        "Transcript")
        self._tabs.addTab(self._build_history_tab(),                           "History")
        self._tabs.addTab(self._build_profile_tab(),                           "Profile")
        return self._tabs

    # ── Tab builders ──────────────────────────────────────────────────────

    def _build_overview_tab(self):
        page = QWidget()
        lay  = QVBoxLayout(page)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        top = QHBoxLayout()
        self._overall_label = QLabel("—")
        self._overall_label.setObjectName("OverallScore")
        self._overall_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addStretch()
        top.addWidget(self._overall_label)
        stats = QVBoxLayout()
        self._dur_lbl = QLabel("Duration: —")
        self._wc_lbl  = QLabel("Words: —")
        self._wpm_lbl = QLabel("WPM: —")
        for l in (self._dur_lbl, self._wc_lbl, self._wpm_lbl):
            l.setStyleSheet("font-size:13px;color:#546E7A;")
            stats.addWidget(l)
        stats.addStretch()
        top.addLayout(stats)
        top.addStretch()
        lay.addLayout(top)

        lay.addWidget(_hdr("Overall Assessment"))
        self._assessment_lbl = QLabel("Record a session to see coaching feedback.")
        self._assessment_lbl.setWordWrap(True)
        self._assessment_lbl.setStyleSheet("font-size:13px;")
        lay.addWidget(self._assessment_lbl)

        row = QHBoxLayout()
        ki = _infobox("Key Insight", "—")
        self._insight_lbl = ki.findChild(QLabel, "InfoValue")
        nf = _infobox("Next Focus", "—")
        self._focus_lbl = nf.findChild(QLabel, "InfoValue")
        row.addWidget(ki)
        row.addWidget(nf)
        lay.addLayout(row)

        lay.addWidget(_hdr("Strengths"))
        self._strengths_lbl = QLabel("—")
        self._strengths_lbl.setWordWrap(True)
        lay.addWidget(self._strengths_lbl)

        lay.addWidget(_hdr("Improvements"))
        self._improvements_lbl = QLabel("—")
        self._improvements_lbl.setWordWrap(True)
        lay.addWidget(self._improvements_lbl)

        lay.addStretch()
        return page

    def _build_dim_tab(self, dim: Dimension):
        page = QWidget()
        lay  = QVBoxLayout(page)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        score_lbl = QLabel("—")
        score_lbl.setObjectName("DimensionScore")
        score_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_lbl.setStyleSheet("font-size:36px;font-weight:700;")

        feedback_lbl = QLabel("Record a session to see feedback.")
        feedback_lbl.setWordWrap(True)
        feedback_lbl.setStyleSheet("font-size:13px;")

        metrics_lbl = QLabel("")
        metrics_lbl.setWordWrap(True)
        metrics_lbl.setStyleSheet("font-size:12px;color:#546E7A;")

        insight_list = QListWidget()
        insight_list.setMaximumHeight(100)

        lay.addWidget(_hdr(str(dim).replace("_", " ").title()))
        lay.addWidget(score_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(feedback_lbl)
        lay.addWidget(_hdr("Metrics"))
        lay.addWidget(metrics_lbl)
        lay.addWidget(_hdr("Insights"))
        lay.addWidget(insight_list)
        lay.addStretch()

        self._dim_widgets[dim] = {
            "score": score_lbl, "feedback": feedback_lbl,
            "metrics": metrics_lbl, "insights": insight_list,
        }
        return page

    def _build_transcript_tab(self):
        self._transcript_view = TranscriptView()
        return self._transcript_view

    def _build_history_tab(self):
        page = QWidget()
        lay  = QVBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        self._trend_dashboard = TrendDashboard(store=self._store)
        lay.addWidget(self._trend_dashboard)

        self._history_table = QTableWidget()
        self._history_table.setColumnCount(7)
        self._history_table.setHorizontalHeaderLabels(
            ["Date", "Duration", "Words", "WPM", "Score", "Best dim", "Weakest dim"]
        )
        self._history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._history_table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self._history_table)
        return page

    def _build_profile_tab(self):
        page = QWidget()
        lay  = QVBoxLayout(page)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        self._profile_narrative = QLabel("")
        self._profile_narrative.setObjectName("ProfileNarrative")
        self._profile_narrative.setWordWrap(True)
        self._profile_narrative.hide()
        lay.addWidget(self._profile_narrative)

        for attr, header in [
            ("_profile_strengths",  "Consistent Strengths"),
            ("_profile_weaknesses", "Recurring Challenges"),
            ("_profile_fillers",    "Persistent Fillers"),
        ]:
            lay.addWidget(_hdr(header))
            lbl = QLabel("—")
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-size:13px;")
            setattr(self, attr, lbl)
            lay.addWidget(lbl)

        lay.addWidget(_hdr("Notable Pattern"))
        self._profile_notable = QLabel("—")
        self._profile_notable.setWordWrap(True)
        lay.addWidget(self._profile_notable)

        lay.addWidget(_hdr("Trends"))
        self._profile_trends = QLabel("—")
        self._profile_trends.setWordWrap(True)
        lay.addWidget(self._profile_trends)

        lay.addStretch()
        return page

    # ── Recording ─────────────────────────────────────────────────────────

    def start_recording(self):
        from core.recorder import AudioRecorder, RecorderError
        import config
        try:
            self._recorder = AudioRecorder(output_dir=str(config.RECORDINGS_DIR))
            self._recorder.start()
        except RecorderError as e:
            self._status_bar.showMessage(f"Recorder error: {e}")
            self._recorder = None
            return
        self._record_stack.setCurrentIndex(1)
        self._elapsed_timer.start(500)
        self._status_bar.showMessage("Recording…")

    def stop_recording(self):
        if self._recorder is None:
            return
        self._elapsed_timer.stop()
        recording = self._recorder.stop()
        self._recorder = None
        self._record_stack.setCurrentIndex(2)
        self._proc_label.setText("Processing…")
        self._status_bar.showMessage("Processing…")
        self._start_pipeline(recording)

    def _tick_elapsed(self):
        if self._recorder:
            s = int(self._recorder.elapsed_seconds)
            self._elapsed_label.setText(f"{s//60}:{s%60:02d}")

    # ── Pipeline ──────────────────────────────────────────────────────────

    def _start_pipeline(self, recording):
        self._worker = PipelineWorker(self._pipeline, recording)
        self._worker.stage_changed.connect(self._on_stage)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_stage(self, text: str):
        self._proc_label.setText(f"{text}…")
        self._status_bar.showMessage(text)

    def _on_failed(self, msg: str):
        self._record_stack.setCurrentIndex(0)
        self._status_bar.showMessage(f"Error: {msg}")

    def _on_finished(self, result: SessionResult):
        self._record_stack.setCurrentIndex(0)
        self._status_bar.showMessage(
            f"Session {result.session_id} — score {result.analytics.overall_score:.0f}/100"
        )
        self._populate_overview(result)
        self._populate_dims(result)
        self._populate_transcript(result)
        self._populate_profile(result)
        self.refresh_history()
        self._update_session_count()

    # ── Populate ──────────────────────────────────────────────────────────

    def _populate_overview(self, r: SessionResult):
        score = r.analytics.overall_score
        colour = score_colour(score)
        self._overall_label.setText(f"{score:.0f}")
        self._overall_label.setStyleSheet(
            f"font-size:48px;font-weight:700;color:{colour};"
        )
        dur = r.recording.duration_seconds
        self._dur_lbl.setText(f"Duration: {int(dur//60)}m {int(dur%60)}s")
        self._wc_lbl.setText(f"Words: {r.transcription.word_count}")
        self._wpm_lbl.setText(f"WPM: {r.transcription.speaking_rate_wpm:.0f}")
        self._assessment_lbl.setText(r.coaching.overall_assessment)
        if self._insight_lbl:
            self._insight_lbl.setText(r.coaching.key_insight)
        if self._focus_lbl:
            self._focus_lbl.setText(r.coaching.next_focus)
        self._strengths_lbl.setText("\n".join(f"✓ {s}" for s in r.coaching.strengths))
        self._improvements_lbl.setText("\n".join(f"→ {s}" for s in r.coaching.improvements))

    def _populate_dims(self, r: SessionResult):
        for dim_result in r.analytics.dimensions:
            w = self._dim_widgets.get(dim_result.dimension)
            if not w:
                continue
            colour = score_colour(dim_result.score)
            w["score"].setText(f"{dim_result.score:.0f}")
            w["score"].setStyleSheet(f"font-size:36px;font-weight:700;color:{colour};")
            w["feedback"].setText(dim_result.feedback)
            metrics_text = "  ·  ".join(f"{k}: {v}" for k, v in dim_result.metrics.items())
            w["metrics"].setText(metrics_text)
            w["insights"].clear()
            for insight in dim_result.insights:
                w["insights"].addItem(f"{insight.insight_type}  —  {insight.value}")

    def _populate_transcript(self, r: SessionResult):
        words = self._store.session_words(r.session_id)
        fe    = {}
        for dim in r.analytics.dimensions:
            if str(dim.dimension) == "fluency":
                fe = dim.filler_events
        segs   = self._store.session_segments(r.session_id)
        pauses = sum(
            1 for i in range(1, len(words))
            if float(words[i]["start"]) - float(words[i - 1]["end"]) > 0.5
        )
        if words:
            self._transcript_view.populate(words, fe, len(segs), pauses)
        else:
            self._transcript_view.populate_from_text(r.transcription.text, fe)

    def _populate_profile(self, r: SessionResult):
        p = r.profile
        if p.narrative:
            self._profile_narrative.setText(p.narrative)
            self._profile_narrative.show()
        else:
            self._profile_narrative.hide()
        self._profile_strengths.setText(
            "\n".join(f"✓ {s}" for s in p.strengths) or "Keep recording to discover strengths.")
        self._profile_weaknesses.setText(
            "\n".join(f"→ {w}" for w in p.recurring_weaknesses) or "No recurring challenges yet.")
        if p.persistent_fillers:
            self._profile_fillers.setText(
                "\n".join(f"{f['word']} — {f['total']} total, {f['sessions_with']} sessions"
                          for f in p.persistent_fillers))
        else:
            self._profile_fillers.setText("No persistent fillers.")
        self._profile_notable.setText(p.notable_pattern or "—")
        if p.trends:
            self._profile_trends.setText(
                "\n".join(f"{d.replace('_',' ').title()}: {t}" for d, t in p.trends.items()))

    def refresh_history(self):
        sessions = self._store.all_sessions_summary()
        self._history_table.setRowCount(len(sessions))
        for row, s in enumerate(sessions):
            dt  = datetime.fromisoformat(str(s["created_at"])) if s.get("created_at") else None
            dur = s.get("duration_seconds", 0)
            overall = s.get("overall_score", 0.0) or 0.0
            detail  = self._store.session_detail(s["id"]) if s.get("id") else {}
            dims    = {a["dimension"]: a["score"] for a in detail.get("analytics", [])}
            best    = max(dims, key=dims.get, default=None) if dims else None
            worst   = min(dims, key=dims.get, default=None) if dims else None
            for col, val in enumerate([
                dt.strftime("%Y-%m-%d %H:%M") if dt else "—",
                f"{int(dur//60)}m {int(dur%60)}s",
                str(s.get("word_count", 0)),
                f"{s.get('speaking_rate_wpm', 0.0):.0f}",
                f"{overall:.0f}",
                best or "—",
                worst or "—",
            ]):
                self._history_table.setItem(row, col, QTableWidgetItem(val))
        self._trend_dashboard.refresh()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _update_session_count(self):
        self._session_count_label.setText(self._session_count_text())

    def _session_count_text(self):
        n = self._store.session_count()
        return f"{n} session{'s' if n != 1 else ''} recorded"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hdr(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("SectionHeader")
    return lbl


def _infobox(title: str, value: str) -> QGroupBox:
    box = QGroupBox(title)
    lay = QVBoxLayout(box)
    val = QLabel(value)
    val.setObjectName("InfoValue")
    val.setWordWrap(True)
    val.setStyleSheet("font-size:13px;")
    lay.addWidget(val)
    return box
