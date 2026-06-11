"""
main.py

Comm Coach application entry point.
"""

from __future__ import annotations

import logging
import sys

from PyQt6.QtWidgets import QApplication

import config

from core.memory import MemoryStore
from core.memory_engine import MemoryEngine
from core.recorder import AudioRecorder
from core.transcriber import make_transcriber
from core.analyzer import make_coach
from core.pipeline import SessionPipeline

from ui.app import MainWindow
from ui.theme import STYLESHEET


def main() -> None:

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s "
            "%(message)s"
        ),
    )

    app = QApplication(sys.argv)

    app.setStyleSheet(STYLESHEET)

    store = MemoryStore(
        config.DB_PATH
    )

    engine = MemoryEngine(
        store
    )

    transcriber = make_transcriber(
        config
    )

    coach = make_coach(
        config
    )

    pipeline = SessionPipeline(
        transcriber=transcriber,
        coach=coach,
        store=store,
        engine=engine,
    )

    recorder = AudioRecorder(
        output_dir=str(
            config.RECORDINGS_DIR
        )
    )

    window = MainWindow(
        pipeline=pipeline,
        recorder=recorder,
        store=store,
    )

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()