# core/memory.py
from __future__ import annotations

import json
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


class MemoryStore:
    """
    Sole SQLite interface for Comm Coach.
    Every read and write goes through here — no other module touches sqlite3.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(
            str(self._db_path),
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,   # UI thread reads; pipeline worker writes
        )
        self._conn.row_factory = sqlite3.Row  # dict-like access on all rows

        self._configure()
        self._create_schema()
        self.upgrade_schema()

        logger.debug("MemoryStore ready at %s", self._db_path)

    # ------------------------------------------------------------------
    # Internal setup
    # ------------------------------------------------------------------

    def _configure(self) -> None:
        """Connection-level PRAGMAs. Run before any DDL or DML."""
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA synchronous = NORMAL")   # safe with WAL

    def _create_schema(self) -> None:
        """Idempotent DDL. Safe to run on every launch."""
        with self._conn:
            self._conn.executescript("""

                -- ── Schema versioning ────────────────────────────────
                CREATE TABLE IF NOT EXISTS meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                INSERT OR IGNORE INTO meta (key, value)
                VALUES ('schema_version', '1');


                -- ── Core session record ───────────────────────────────
                CREATE TABLE IF NOT EXISTS sessions (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    duration_seconds   REAL      NOT NULL,
                    recording_path     TEXT      NOT NULL,
                    video_path         TEXT,
                    transcript         TEXT      NOT NULL,
                    word_count         INTEGER   NOT NULL,
                    speaking_rate_wpm  REAL      NOT NULL,
                    overall_score      REAL      NOT NULL
                );


                -- ── Per-dimension analytics ───────────────────────────
                CREATE TABLE IF NOT EXISTS analytics (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    dimension   TEXT    NOT NULL CHECK (dimension IN (
                                    'fluency', 'clarity', 'expression',
                                    'speech_signal_clarity', 'conciseness'
                                )),
                    metrics     TEXT    NOT NULL,
                    score       REAL    NOT NULL CHECK (score BETWEEN 0 AND 100),
                    feedback    TEXT    NOT NULL,
                    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (session_id, dimension)
                );


                -- ── Filler word counts per session ────────────────────
                CREATE TABLE IF NOT EXISTS filler_events (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    word        TEXT    NOT NULL,
                    count       INTEGER NOT NULL CHECK (count > 0),
                    UNIQUE (session_id, word)
                );


                -- ── Discrete queryable patterns per session ───────────
                CREATE TABLE IF NOT EXISTS session_insights (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id    INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    insight_type  TEXT    NOT NULL CHECK (insight_type IN (
                                      'overuses_filler', 'talks_too_fast', 'topic_drift',
                                      'strong_vocabulary', 'verbose_phrases',
                                      'repeated_ideas', 'low_signal_clarity'
                                  )),
                    value         TEXT    NOT NULL,
                    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );


                -- ── Vector embeddings — empty in v1, populated in v1.5 ─
                CREATE TABLE IF NOT EXISTS session_embeddings (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    embedding   BLOB    NOT NULL,
                    model       TEXT    NOT NULL,
                    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (session_id)
                );


                -- ── Indexes ───────────────────────────────────────────
                CREATE INDEX IF NOT EXISTS idx_sessions_created
                    ON sessions(created_at DESC);

                CREATE INDEX IF NOT EXISTS idx_analytics_session
                    ON analytics(session_id);

                CREATE INDEX IF NOT EXISTS idx_analytics_dim_session
                    ON analytics(dimension, session_id);

                CREATE INDEX IF NOT EXISTS idx_fillers_word
                    ON filler_events(word);

                CREATE INDEX IF NOT EXISTS idx_insights_type
                    ON session_insights(insight_type);

                CREATE INDEX IF NOT EXISTS idx_insights_session
                    ON session_insights(session_id);

            """)

    def upgrade_schema(self) -> None:
        """
        Migration hook for v1.5 / v2.
        Reads meta.schema_version and applies incremental migrations.
        No migrations exist in v1 — this is infrastructure only.
        """
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        current = int(row["value"]) if row else 0

        # Future migrations slot in here as:
        #   if current < 2: ...apply migration... current = 2
        # For now, just ensure the stored version is current.
        if current < SCHEMA_VERSION:
            with self._conn:
                self._conn.execute(
                    "UPDATE meta SET value = ? WHERE key = 'schema_version'",
                    (str(SCHEMA_VERSION),),
                )
            logger.info("Schema upgraded to version %s", SCHEMA_VERSION)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def save_session(
        self,
        recording,       # RecordingResult
        transcription,   # TranscriptionResult
        analytics,       # AnalyticsBundle
        coaching,        # CoachingResult
    ) -> int:
        """
        Persist a complete session atomically.
        Writes: sessions row, 5 analytics rows, filler_events, session_insights.
        All-or-nothing — rolls back entirely on any failure.
        Returns the new session_id.
        """
        with self._conn:
            # 1. sessions row
            cursor = self._conn.execute(
                """
                INSERT INTO sessions (
                    created_at, duration_seconds, recording_path,
                    transcript, word_count, speaking_rate_wpm, overall_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recording.created_at,
                    recording.duration_seconds,
                    recording.wav_path,
                    transcription.text,
                    transcription.word_count,
                    transcription.speaking_rate_wpm,
                    analytics.overall_score,
                ),
            )
            session_id = cursor.lastrowid

            # 2. Five analytics rows + fillers + insights — one pass over dimensions
            for dim in analytics.dimensions:
                self._conn.execute(
                    """
                    INSERT INTO analytics (session_id, dimension, metrics, score, feedback)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        str(dim.dimension),       # Dimension enum → str
                        json.dumps(dim.metrics),
                        dim.score,
                        dim.feedback,
                    ),
                )

                # filler_events only populated on fluency, but guard is universal
                if dim.filler_events:
                    self._conn.executemany(
                        """
                        INSERT INTO filler_events (session_id, word, count)
                        VALUES (?, ?, ?)
                        """,
                        [
                            (session_id, word, count)
                            for word, count in dim.filler_events.items()
                            if count > 0
                        ],
                    )

                if dim.insights:
                    self._conn.executemany(
                        """
                        INSERT INTO session_insights (session_id, insight_type, value)
                        VALUES (?, ?, ?)
                        """,
                        [
                            (session_id, str(insight.insight_type), insight.value)
                            for insight in dim.insights
                        ],
                    )

        logger.debug(
            "Saved session %s (overall %.1f, %s words)",
            session_id,
            analytics.overall_score,
            transcription.word_count,
        )
        return session_id

    def session_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM sessions").fetchone()
        return row["n"]

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def recent_sessions(self, limit: int = 5) -> list[dict]:
        """
        Last N sessions with per-dimension scores pivoted into one row each.
        Returned newest-first. Consumed by Memory Engine to build LLM context.
        """
        rows = self._conn.execute(
            """
            SELECT
                s.id,
                s.created_at,
                s.word_count,
                s.speaking_rate_wpm,
                s.overall_score,
                MAX(CASE WHEN a.dimension = 'fluency'               THEN a.score END) AS fluency,
                MAX(CASE WHEN a.dimension = 'clarity'               THEN a.score END) AS clarity,
                MAX(CASE WHEN a.dimension = 'expression'            THEN a.score END) AS expression,
                MAX(CASE WHEN a.dimension = 'speech_signal_clarity' THEN a.score END) AS ssc,
                MAX(CASE WHEN a.dimension = 'conciseness'           THEN a.score END) AS conciseness
            FROM sessions s
            JOIN analytics a ON a.session_id = s.id
            GROUP BY s.id
            ORDER BY s.created_at DESC, s.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def all_sessions_summary(self) -> list[dict]:
        """
        All sessions, newest first. Used by the History tab.
        Reads overall_score directly from sessions — no join needed.
        """
        rows = self._conn.execute(
            """
            SELECT id, created_at, duration_seconds,
                   word_count, speaking_rate_wpm, overall_score
            FROM sessions
            ORDER BY created_at DESC, id DESC
            """,
        ).fetchall()
        return [dict(r) for r in rows]

    def session_detail(self, session_id: int) -> dict:
        """
        Full detail for one session: session row + analytics + fillers + insights.
        Returns {} if session_id not found.
        """
        session = self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()

        if session is None:
            return {}

        analytics_rows = self._conn.execute(
            """
            SELECT dimension, score, metrics, feedback
            FROM analytics
            WHERE session_id = ?
            ORDER BY dimension
            """,
            (session_id,),
        ).fetchall()

        filler_rows = self._conn.execute(
            """
            SELECT word, count
            FROM filler_events
            WHERE session_id = ?
            ORDER BY count DESC
            """,
            (session_id,),
        ).fetchall()

        insight_rows = self._conn.execute(
            """
            SELECT insight_type, value
            FROM session_insights
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchall()

        return {
            **dict(session),
            "analytics": [dict(r) for r in analytics_rows],
            "fillers":   [dict(r) for r in filler_rows],
            "insights":  [dict(r) for r in insight_rows],
        }

    def dimension_series(self, dimension: str, limit: int = 10) -> list[float]:
        """
        Scores for one dimension across the last N sessions, returned oldest-first.
        Callers split at the midpoint to compare recent vs earlier halves for trends.
        """
        rows = self._conn.execute(
            """
            SELECT a.score
            FROM analytics a
            JOIN sessions s ON s.id = a.session_id
            WHERE a.dimension = ?
            ORDER BY s.created_at DESC, s.id DESC
            LIMIT ?
            """,
            (dimension, limit),
        ).fetchall()
        return list(reversed([r["score"] for r in rows]))   # oldest → newest

    def insight_frequencies(self) -> list[tuple[str, int, int]]:
        """
        Returns (insight_type, sessions_appeared_in, total_occurrences),
        ordered by sessions_appeared_in descending.
        Memory Engine uses this to surface recurring patterns for the LLM.
        """
        rows = self._conn.execute(
            """
            SELECT
                insight_type,
                COUNT(DISTINCT session_id) AS session_count,
                COUNT(*)                   AS total_count
            FROM session_insights
            GROUP BY insight_type
            ORDER BY session_count DESC
            """,
        ).fetchall()
        return [(r["insight_type"], r["session_count"], r["total_count"]) for r in rows]

    def persistent_fillers(self) -> list[dict]:
        """
        Filler words present in more than 50% of all sessions.
        Returns word, sessions_with, total — ordered by total desc.
        Used by Communication Profile.
        """
        rows = self._conn.execute(
            """
            SELECT
                word,
                COUNT(DISTINCT session_id) AS sessions_with,
                SUM(count)                 AS total
            FROM filler_events
            GROUP BY word
            HAVING sessions_with > (SELECT COUNT(*) FROM sessions) / 2.0
            ORDER BY total DESC
            """,
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, *_) -> None:
        self.close()