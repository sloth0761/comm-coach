"""
Standalone validation for MemoryStore. No pytest required.
Run from project root: python scratch/test_memory_store.py
"""
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.memory import MemoryStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dim(name, score, filler_word=None, filler_count=0, insight_type=None, insight_value=None):
    return SimpleNamespace(
        dimension=name,
        score=float(score),
        metrics={"dimension": name, "score": score},
        feedback=f"{name} feedback.",
        filler_events={filler_word: filler_count} if filler_word and filler_count else {},
        insights=(
            (SimpleNamespace(insight_type=insight_type, value=insight_value),)
            if insight_type else ()
        ),
    )


def _make_session(fluency=62.0, filler_word="um", filler_count=4, overall=67.5):
    recording = SimpleNamespace(
        wav_path="data/recordings/test.wav",
        duration_seconds=90.0,
        created_at=datetime.now(),
    )
    transcription = SimpleNamespace(
        text="Um basically I think what I'm trying to say is hello right",
        word_count=12,
        speaking_rate_wpm=148.0,
    )
    analytics = SimpleNamespace(
        dimensions=(
            _make_dim("fluency", fluency, filler_word, filler_count,
                      "overuses_filler", filler_word),
            _make_dim("clarity",               78.0),
            _make_dim("expression",            55.0, insight_type="strong_vocabulary", insight_value="ttr=0.70"),
            _make_dim("speech_signal_clarity", 81.0),
            _make_dim("conciseness",           44.0, insight_type="verbose_phrases", insight_value="3 found"),
        ),
        overall_score=overall,
    )
    coaching = SimpleNamespace(
        overall_assessment="Solid session.",
        strengths=("Good pace",),
        improvements=("Reduce fillers",),
        key_insight=f"You use '{filler_word}' frequently.",
        next_focus="One minute, zero fillers.",
        raw_json="{}",
    )
    return recording, transcription, analytics, coaching


def check(label, condition, detail=""):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def run():
    with tempfile.TemporaryDirectory() as tmp:
        store = MemoryStore(str(Path(tmp) / "test.db"))

        print("\n── T1  Empty state ─────────────────────────────────────")
        check("session_count == 0", store.session_count() == 0)
        check("recent_sessions returns []", store.recent_sessions() == [])
        check("all_sessions_summary returns []", store.all_sessions_summary() == [])
        check("dimension_series returns []", store.dimension_series("fluency") == [])
        check("insight_frequencies returns []", store.insight_frequencies() == [])
        check("persistent_fillers returns []", store.persistent_fillers() == [])
        check("session_detail missing returns {}", store.session_detail(99) == {})

        print("\n── T2  Single insert ───────────────────────────────────")
        sid = store.save_session(*_make_session())
        check("save_session returns 1", sid == 1)
        check("session_count == 1", store.session_count() == 1)

        print("\n── T3  recent_sessions pivot ───────────────────────────")
        recent = store.recent_sessions()
        r = recent[0]
        check("len == 1",           len(recent) == 1)
        check("fluency correct",    r["fluency"] == 62.0,    r.get("fluency"))
        check("clarity correct",    r["clarity"] == 78.0,    r.get("clarity"))
        check("overall_score",      r["overall_score"] == 67.5)
        check("all dims present",   all(k in r for k in ("fluency","clarity","expression","ssc","conciseness")))

        print("\n── T4  all_sessions_summary ────────────────────────────")
        summary = store.all_sessions_summary()
        check("len == 1",           len(summary) == 1)
        check("overall_score key",  "overall_score" in summary[0])
        check("no analytics key",   "analytics" not in summary[0])  # summary stays lean

        print("\n── T5  session_detail ──────────────────────────────────")
        detail = store.session_detail(1)
        check("id correct",         detail["id"] == 1)
        check("5 analytics rows",   len(detail["analytics"]) == 5,  len(detail["analytics"]))
        check("filler word == um",  detail["fillers"][0]["word"] == "um")
        check("filler count == 4",  detail["fillers"][0]["count"] == 4)
        insight_types = [i["insight_type"] for i in detail["insights"]]
        check("overuses_filler insight", "overuses_filler" in insight_types)
        check("verbose_phrases insight", "verbose_phrases" in insight_types)

        print("\n── T6  dimension_series ────────────────────────────────")
        series = store.dimension_series("fluency")
        check("length == 1",        len(series) == 1)
        check("score correct",      series[0] == 62.0)

        print("\n── T7  insight_frequencies ─────────────────────────────")
        freqs = store.insight_frequencies()
        types = [f[0] for f in freqs]
        check("overuses_filler present",  "overuses_filler" in types)
        check("session_count == 1",       freqs[0][1] == 1)

        print("\n── T8  persistent_fillers (multi-session) ──────────────")
        # Three sessions all using "um" → 3/3 = 100% > 50% threshold
        store.save_session(*_make_session())
        store.save_session(*_make_session())
        check("session_count == 3",  store.session_count() == 3)
        pf = store.persistent_fillers()
        check("um is persistent",    len(pf) > 0 and pf[0]["word"] == "um",  pf)
        check("total >= 12",         pf[0]["total"] >= 12)  # 3 sessions × 4 each

        print("\n── T9  dimension_series oldest-first ordering ───────────")
        # Insert a 4th session with a higher fluency score
        store.save_session(*_make_session(fluency=85.0, overall=80.0))
        series = store.dimension_series("fluency", limit=10)
        check("length == 4",         len(series) == 4)
        check("oldest first",        series[0] == 62.0,  series)
        check("newest last",         series[-1] == 85.0, series)

        print("\n── T10  recent_sessions limit ──────────────────────────")
        # 4 sessions exist; limit=2 should return 2
        recent2 = store.recent_sessions(limit=2)
        check("limit respected",     len(recent2) == 2)
        check("newest first",        recent2[0]["overall_score"] == 80.0)

        store.close()
        print("\n✓  All tests passed. Phase 2 complete.\n")


if __name__ == "__main__":
    run()