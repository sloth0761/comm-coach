"""
Comm Coach — entry point.
Wires all components and launches the PyQt6 window.
Run: python main.py
"""
import logging
import sys

from PyQt6.QtWidgets import QApplication

import config
from core.analyzer import make_coach
from core.memory import MemoryStore
from core.memory_engine import MemoryEngine
from core.pipeline import SessionPipeline
from core.recorder import AudioRecorder
from core.transcriber import make_transcriber
from ui.app import MainWindow


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    # Ensure data directories exist
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    app.setApplicationName("Comm Coach")

    # Wire the engine
    store       = MemoryStore(config.DB_PATH)
    engine      = MemoryEngine(store)
    transcriber = make_transcriber(config)
    coach       = make_coach(config)
    pipeline    = SessionPipeline(
        transcriber=transcriber,
        coach=coach,
        store=store,
        engine=engine,
        # on_stage is overwritten per-run by PipelineWorker
    )
    recorder = AudioRecorder(output_dir=str(config.RECORDINGS_DIR))

    window = MainWindow(pipeline=pipeline, recorder=recorder, store=store)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()