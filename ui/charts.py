"""
ui/charts.py

Per-dimension trend sparklines (v1.5), backed by matplotlib's Qt backend.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def score_colour(score: float) -> str:
    if score >= 75:
        return "#2E7D32"
    if score >= 50:
        return "#E65100"
    return "#B71C1C"


try:
    import matplotlib
    matplotlib.use("QtAgg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel
    from PyQt6.QtCore import Qt

    class DimensionTrendChart(QWidget):
        def __init__(self, dimension_name: str, parent=None):
            super().__init__(parent)
            self._dimension_name = dimension_name
            self._fig, self._ax = plt.subplots(figsize=(3.2, 2.0))
            self._canvas = FigureCanvas(self._fig)
            self._fig.patch.set_facecolor("none")
            layout = QVBoxLayout(self)
            layout.setContentsMargins(4, 4, 4, 4)
            title = QLabel(dimension_name.replace("_", " ").title())
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title.setStyleSheet("font-size:11px;color:#546E7A;")
            layout.addWidget(title)
            layout.addWidget(self._canvas)
            self.update([])

        def update(self, scores: list[float]) -> None:
            ax = self._ax
            ax.clear()
            ax.set_facecolor("#FAFAFA")
            ax.set_ylim(0, 100)
            ax.tick_params(labelsize=7)
            ax.spines[["top", "right"]].set_visible(False)
            if len(scores) >= 2:
                xs = list(range(1, len(scores) + 1))
                colour = score_colour(scores[-1])
                ax.plot(xs, scores, color=colour, linewidth=1.5, marker="o",
                        markersize=4, markerfacecolor=colour)
                ax.axhline(y=sum(scores) / len(scores), color="#B0BEC5",
                           linewidth=0.8, linestyle="--")
            elif len(scores) == 1:
                ax.plot([1], scores, color=score_colour(scores[0]),
                        marker="o", markersize=6)
            self._fig.tight_layout(pad=0.4)
            self._canvas.draw_idle()

    class TrendDashboard(QWidget):
        _DIMS = ("fluency", "clarity", "expression", "speech_signal_clarity", "conciseness")

        def __init__(self, store, parent=None):
            super().__init__(parent)
            self._store = store
            grid = QGridLayout(self)
            grid.setSpacing(4)
            self._charts: dict[str, DimensionTrendChart] = {}
            for i, dim in enumerate(self._DIMS):
                chart = DimensionTrendChart(dim)
                self._charts[dim] = chart
                grid.addWidget(chart, i // 2, i % 2)

        def refresh(self) -> None:
            for dim, chart in self._charts.items():
                try:
                    scores = self._store.dimension_series(dim, limit=10)
                    chart.update(scores)
                except Exception as exc:
                    logger.warning("Chart refresh failed for %s: %s", dim, exc)

except ImportError as _e:
    logger.warning("charts unavailable: %s", _e)

    class DimensionTrendChart:   # type: ignore[no-redef]
        def __init__(self, *a, **k): ...
        def update(self, scores): ...

    class TrendDashboard:   # type: ignore[no-redef]
        def __init__(self, *a, **k): ...
        def refresh(self): ...
