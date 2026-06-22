"""
ui/transcript_view.py

Word-level annotated transcript view (v1.5).
Highlights fillers, low-confidence words, and pauses using word-level
timestamps from Whisper. Falls back to plain-text filler highlighting when
no word-level data is available (v1 sessions).
"""
from __future__ import annotations

import html as _html
import logging
import re

logger = logging.getLogger(__name__)

FILLER_WORDS: frozenset[str] = frozenset({
    "um", "uh", "ah", "er", "like", "basically", "literally",
    "actually", "right", "so", "well", "okay", "hmm", "you", "know",
})
MULTI_WORD_FILLERS: list[str] = ["you know", "kind of", "sort of", "i mean"]
_MWF_PAIRS = frozenset(tuple(p.split()) for p in MULTI_WORD_FILLERS)

LOW_PROB_THRESHOLD = 0.55
PAUSE_THRESHOLD_S  = 0.5

_AMBER = "#FFE082"
_BROWN = "#5D4037"
_RED   = "#E53935"
_GREY  = "#9E9E9E"
_DARK  = "#212121"


def _mark(text):
    return f"<mark style='background:{_AMBER};color:{_BROWN};border-radius:2px;padding:0 2px;'>{text}</mark>"


def _low(text, prob):
    return f"<span style='color:{_RED};' title='Low confidence: {prob:.2f}'>{text}</span>"


def _pause(gap):
    return f" <span style='color:{_GREY};font-size:11px;' title='Pause: {gap:.2f}s'>[{gap:.1f}s]</span> "


def _body(inner):
    return f"<body style='font-family:monospace;font-size:14px;line-height:1.8;color:{_DARK};'>{inner}</body>"


class TranscriptAnnotator:
    def build_html(self, words: list[dict], filler_events: dict) -> str:
        if not words:
            return "<p><em>No word-level data for this session.</em></p>"
        fillers = FILLER_WORDS | frozenset(w.lower() for w in (filler_events or {}))
        parts, i = [], 0
        while i < len(words):
            w = words[i]
            wl = w["word"].strip().lower()
            # multi-word filler
            if i + 1 < len(words):
                nl = words[i + 1]["word"].strip().lower()
                if (wl, nl) in _MWF_PAIRS:
                    parts.append(_mark(_html.escape(w["word"] + words[i + 1]["word"])))
                    if i + 2 < len(words):
                        g = words[i + 2]["start"] - words[i + 1]["end"]
                        if g > PAUSE_THRESHOLD_S:
                            parts.append(_pause(g))
                    i += 2
                    continue
            esc  = _html.escape(w["word"])
            prob = float(w.get("probability", 1.0))
            if wl in fillers:
                parts.append(_mark(esc))
            elif prob <= LOW_PROB_THRESHOLD:
                parts.append(_low(esc, prob))
            else:
                parts.append(esc)
            if i + 1 < len(words):
                g = float(words[i + 1]["start"]) - float(w["end"])
                if g > PAUSE_THRESHOLD_S:
                    parts.append(_pause(g))
            i += 1
        return _body("".join(parts))

    def build_html_from_text(self, text: str, filler_events: dict) -> str:
        if not text:
            return "<p><em>No transcript available.</em></p>"
        fillers = FILLER_WORDS | frozenset(w.lower() for w in (filler_events or {}))
        escaped = _html.escape(text)
        for f in sorted(fillers, key=len, reverse=True):
            escaped = re.sub(r'\b' + re.escape(f) + r'\b',
                              lambda m: _mark(m.group(0)),
                              escaped, flags=re.IGNORECASE)
        return _body(escaped)


try:
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit

    class TranscriptView(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._ann = TranscriptAnnotator()
            layout = QVBoxLayout(self)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(8)

            leg = QHBoxLayout()
            for label, style in [
                ("■ Filler",         f"background:{_AMBER};color:{_BROWN};padding:2px 6px;border-radius:3px;font-size:12px;"),
                ("■ Low confidence", f"color:{_RED};font-size:12px;font-weight:bold;"),
                ("| Pause (>0.5s)",  f"color:{_GREY};font-size:12px;"),
            ]:
                lbl = QLabel(label)
                lbl.setStyleSheet(style)
                leg.addWidget(lbl)
            leg.addStretch()
            layout.addLayout(leg)

            self._stats = QLabel("—")
            self._stats.setStyleSheet("font-size:12px;color:#666;")
            layout.addWidget(self._stats)

            self._edit = QTextEdit()
            self._edit.setObjectName("TranscriptEdit")
            self._edit.setReadOnly(True)
            self._edit.setPlaceholderText("Record a session to see your annotated transcript.")
            layout.addWidget(self._edit)

        def populate(self, words, filler_events, segment_count, pause_count):
            if words:
                self._edit.setHtml(self._ann.build_html(words, filler_events))
                fc = sum(filler_events.values()) if filler_events else 0
                lc = sum(1 for w in words if float(w.get("probability", 1.0)) <= LOW_PROB_THRESHOLD)
                self._stats.setText(f"{fc} fillers · {pause_count} pauses · {lc} low-confidence · {segment_count} segments")
            else:
                self._edit.setHtml(self._ann.build_html([], filler_events))
                self._stats.setText("Word-level data unavailable for this session.")

        def populate_from_text(self, text, filler_events):
            self._edit.setHtml(self._ann.build_html_from_text(text, filler_events))
            self._stats.setText("Text-search approximation (no word timestamps).")

        def clear(self):
            self._edit.clear()
            self._stats.setText("—")

except ImportError:
    class TranscriptView:   # type: ignore[no-redef]
        def __init__(self, *a, **k): ...
        def populate(self, *a, **k): ...
        def populate_from_text(self, *a, **k): ...
        def clear(self): ...
