import sqlite3
from pathlib import Path


class MemoryStore:
    def __init__(self, db_path: str):
        self.db_path = db_path

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(
            db_path,
            check_same_thread=False,
        )

        self.conn.row_factory = sqlite3.Row

        self._configure()
        self._create_tables()

    def _configure(self):
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")

    def _create_tables(self):
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """)

        self.conn.execute("""
        INSERT OR IGNORE INTO meta(key, value)
        VALUES ('schema_version', '1')
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            duration_seconds REAL NOT NULL,
            recording_path TEXT NOT NULL,
            video_path TEXT,
            transcript TEXT NOT NULL,
            word_count INTEGER NOT NULL,
            speaking_rate_wpm REAL NOT NULL,
            overall_score REAL NOT NULL
        )
        """)

        self.conn.commit()

    def session_count(self):
        row = self.conn.execute(
            "SELECT COUNT(*) AS count FROM sessions"
        ).fetchone()

        return row["count"]

    def save_mock_session(self):
        cursor = self.conn.execute("""
        INSERT INTO sessions (
            duration_seconds,
            recording_path,
            transcript,
            word_count,
            speaking_rate_wpm,
            overall_score
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            60.0,
            "data/recordings/mock.wav",
            "Hello this is a mock session.",
            6,
            120.0,
            85.0,
        ))

        self.conn.commit()

        return cursor.lastrowid