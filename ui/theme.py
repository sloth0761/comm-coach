"""
ui/theme.py

Application styling and visual helpers.
"""

from __future__ import annotations


def score_colour(score: float) -> str:
    """
    Score colour helper used throughout the UI.

    >= 75  -> green
    >= 50  -> amber
    <  50  -> red
    """
    if score >= 75:
        return "#4CAF50"

    if score >= 50:
        return "#FF9800"

    return "#F44336"


STYLESHEET = """
QMainWindow {
    background: #F5F6F8;
}

QWidget {
    font-size: 14px;
    color: #222222;
}

QTabWidget::pane {
    border: 1px solid #D8D8D8;
    background: white;
}

QTabBar::tab {
    background: #ECECEC;
    padding: 8px 14px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: white;
    font-weight: bold;
}

QStatusBar {
    background: white;
}

QFrame#ScoreCard {
    background: white;
    border: 1px solid #DADADA;
    border-radius: 8px;
    padding: 8px;
}

QFrame#CalloutBox {
    background: #F7F7F7;
    border-left: 4px solid #4CAF50;
    border-radius: 6px;
    padding: 10px;
}

QFrame#FocusBox {
    background: #FFF9E8;
    border-left: 4px solid #FF9800;
    border-radius: 6px;
    padding: 10px;
}

QLabel#HeaderTitle {
    font-size: 28px;
    font-weight: bold;
}

QLabel#OverallScore {
    font-size: 42px;
    font-weight: bold;
}

QLabel#DimensionScore {
    font-size: 26px;
    font-weight: bold;
}

QLabel#ScoreTitle {
    font-size: 13px;
    color: #666666;
}

QLabel#TagLabel {
    background: #E9EEF8;
    border-radius: 10px;
    padding: 4px 10px;
}

QPushButton#RecordButton {
    min-width: 140px;
    max-width: 140px;
    min-height: 140px;
    max-height: 140px;
    border-radius: 70px;
    font-size: 20px;
    font-weight: bold;
    background: #607D8B;
    color: white;
}

QPushButton#RecordButton[recording="true"] {
    background: #F44336;
}

QPushButton#RecordButton[processing="true"] {
    background: #9E9E9E;
}

QTableWidget {
    background: white;
    gridline-color: #DDDDDD;
}

QHeaderView::section {
    background: #F0F0F0;
    font-weight: bold;
}
"""