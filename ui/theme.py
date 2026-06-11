"""
Application theme.
Applied once at startup: app.setStyleSheet(STYLESHEET)
score_color() is used inline wherever a score drives a colour.
"""
from __future__ import annotations

# Colour palette
C_BG          = "#F5F5F5"
C_SURFACE     = "#FFFFFF"
C_BORDER      = "#E0E0E0"
C_TEXT        = "#212121"
C_TEXT_LIGHT  = "#757575"
C_GREEN       = "#2E7D32"
C_GREEN_BG    = "#E8F5E9"
C_AMBER       = "#E65100"
C_AMBER_BG    = "#FFF3E0"
C_RED         = "#C62828"
C_RED_BG      = "#FFEBEE"
C_ACCENT      = "#1565C0"
C_RECORD      = "#C62828"
C_RECORD_BG   = "#FFEBEE"
C_DISABLED    = "#9E9E9E"


def score_color(score: float) -> str:
    """Return a CSS hex colour for a 0–100 score."""
    if score >= 75:
        return C_GREEN
    if score >= 50:
        return C_AMBER
    return C_RED


def score_bg(score: float) -> str:
    """Return a background CSS hex colour for a score card."""
    if score >= 75:
        return C_GREEN_BG
    if score >= 50:
        return C_AMBER_BG
    return C_RED_BG


STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {C_BG};
    color: {C_TEXT};
    font-family: -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 14px;
}}

/* Header */
#header {{
    background-color: {C_SURFACE};
    border-bottom: 1px solid {C_BORDER};
    padding: 12px 20px;
}}
#app_title {{
    font-size: 20px;
    font-weight: bold;
    color: {C_ACCENT};
}}
#session_count {{
    color: {C_TEXT_LIGHT};
    font-size: 13px;
}}

/* Record area */
#record_area {{
    background-color: {C_SURFACE};
    border-bottom: 1px solid {C_BORDER};
    padding: 20px;
}}
#record_button {{
    min-width: 120px;
    min-height: 120px;
    max-width: 120px;
    max-height: 120px;
    border-radius: 60px;
    font-size: 16px;
    font-weight: bold;
    border: 3px solid {C_ACCENT};
    background-color: {C_SURFACE};
    color: {C_ACCENT};
}}
#record_button:hover {{
    background-color: #E3F2FD;
}}
#record_button[state="recording"] {{
    border-color: {C_RECORD};
    background-color: {C_RECORD_BG};
    color: {C_RECORD};
}}
#record_button[state="processing"] {{
    border-color: {C_DISABLED};
    background-color: {C_BG};
    color: {C_DISABLED};
}}
#elapsed_label {{
    font-size: 28px;
    font-weight: bold;
    color: {C_TEXT};
    min-width: 80px;
}}
#stage_label {{
    color: {C_TEXT_LIGHT};
    font-size: 13px;
}}

/* Tabs */
QTabWidget::pane {{
    border: none;
    background-color: {C_BG};
}}
QTabBar::tab {{
    padding: 8px 16px;
    background-color: {C_BG};
    border-bottom: 2px solid transparent;
    color: {C_TEXT_LIGHT};
}}
QTabBar::tab:selected {{
    color: {C_ACCENT};
    border-bottom: 2px solid {C_ACCENT};
    font-weight: bold;
}}

/* Score cards */
#score_card {{
    background-color: {C_SURFACE};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    padding: 12px;
    min-width: 120px;
}}

/* Insight callout */
#key_insight_box {{
    background-color: #E3F2FD;
    border-left: 4px solid {C_ACCENT};
    border-radius: 4px;
    padding: 12px 16px;
}}
#next_focus_box {{
    background-color: {C_GREEN_BG};
    border-left: 4px solid {C_GREEN};
    border-radius: 4px;
    padding: 12px 16px;
}}

/* Filler tags */
#filler_tag {{
    background-color: {C_AMBER_BG};
    border: 1px solid {C_AMBER};
    border-radius: 12px;
    padding: 3px 10px;
    color: {C_AMBER};
    font-size: 13px;
}}

/* Section headers */
#section_header {{
    font-size: 13px;
    font-weight: bold;
    color: {C_TEXT_LIGHT};
    text-transform: uppercase;
    letter-spacing: 1px;
    padding-top: 8px;
}}

/* History table */
QTableWidget {{
    background-color: {C_SURFACE};
    border: 1px solid {C_BORDER};
    gridline-color: {C_BORDER};
    border-radius: 4px;
}}
QTableWidget::item {{
    padding: 6px 12px;
}}
QHeaderView::section {{
    background-color: {C_BG};
    border: none;
    border-bottom: 1px solid {C_BORDER};
    padding: 6px 12px;
    font-weight: bold;
    color: {C_TEXT_LIGHT};
    font-size: 12px;
}}

/* Scrollbars */
QScrollBar:vertical {{
    width: 8px;
    background: transparent;
}}
QScrollBar::handle:vertical {{
    background: {C_BORDER};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* General */
QLabel#placeholder {{
    color: {C_TEXT_LIGHT};
    font-style: italic;
}}
QScrollArea {{
    border: none;
    background-color: transparent;
}}
"""