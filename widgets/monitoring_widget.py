"""Right column: summary badges + a PyQtGraph 4-channel ADC1 current chart
with zoom / pan / scale controls.

Chart interaction
-----------------
* Mouse wheel over the plot   : zoom both axes (over an axis: that axis only)
* Left-drag                   : pan
* Right-drag                  : stretch / squash an axis
* Double-click                : reset view (Live + Autoscale, 10 s span)
* Y + / Y -                   : zoom the current axis in / out
* X + / X -                   : shorten / lengthen the time window
* Span box                    : 5 s / 10 s / 30 s / 60 s / All history
* Y min / Y max               : type an exact range
* Live                        : X axis follows the newest sample
* Autoscale                   : Y axis fits the visible data
* Pause                       : freeze the picture (data keeps being buffered)

Any manual pan/zoom on an axis switches that axis out of Live / Autoscale so
the view is never yanked away from you; press the button (or Reset view) to
go back.
"""
import time
from collections import deque

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QVBoxLayout,
)

from config import (
    ADC_CH_COLORS, ADC_CH_LABELS,
    ADC_CURRENT_Y_MIN, ADC_CURRENT_Y_MAX,
)
from theme import (
    ACCENT, BORDER, BORDER_HOVER, INNER_DARK, PANEL, TEXT, TEXT_DIM, TEXT_MUTED,
)

pg.setConfigOptions(antialias=False, background=INNER_DARK, foreground=TEXT_MUTED)

HISTORY_SAMPLES = 3000      # per channel (~1 min at ~50 Hz)
REDRAW_MS       = 16        # chart refresh (~60 fps), decoupled from data rate
BADGE_MIN_INTERVAL_S = 0.1  # number badges update at 10 Hz (unreadable faster)
MIN_Y_SPAN      = 2.0       # mA - smallest Y window the zoom buttons allow
DEFAULT_SPAN_S  = 10.0
SPAN_PRESETS    = [("5 s", 5.0), ("10 s", 10.0), ("30 s", 30.0),
                   ("60 s", 60.0), ("All", None)]

_BTN_QSS = f"""
    QPushButton {{
        background: {PANEL}; color: {TEXT};
        border: 1px solid {BORDER}; border-radius: 12px;
        padding: 4px 11px; font-size: 12px; font-weight: 600;
    }}
    QPushButton:hover    {{ border-color: {BORDER_HOVER}; }}
    QPushButton:checked  {{ background: {ACCENT}; color: #05080B;
                            border-color: {ACCENT}; }}
    QPushButton:disabled {{ color: {TEXT_DIM}; }}
"""

_COMBO_QSS = f"""
    QComboBox {{
        background: {INNER_DARK}; color: {TEXT};
        border: 1px solid {BORDER}; border-radius: 8px;
        padding: 3px 8px; font-size: 12px;
    }}
"""


# --------------------------------------------------------------------- cards

class ChannelBadge(QFrame):
    def __init__(self, label: str, color: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame {{ background: {PANEL}; border: 1px solid {BORDER};"
            f"border-radius: 12px; }}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(8)

        dot = QLabel("\u25cf")
        dot.setStyleSheet(f"color: {color}; font-size: 12px;")
        row.addWidget(dot)

        name = QLabel(label)
        name.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 10px;"
            f"font-weight: 700; letter-spacing: 1.5px;"
        )
        row.addWidget(name)

        self.value_lbl = QLabel("----")
        self.value_lbl.setStyleSheet(
            f"color: {TEXT}; font-size: 18px; font-weight: 700;"
            f"font-family: 'JetBrains Mono', 'Consolas', monospace;"
        )
        self.value_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(self.value_lbl, 1)

    def set_value(self, value: int):
        self.value_lbl.setText(f"{value:d}")


class SummaryRow(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GlassCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(10)

        heading = QLabel("ADC1  \u00b7  CURRENT (mA)")
        heading.setObjectName("Heading")
        outer.addWidget(heading)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.badges = []
        for i in range(4):
            badge = ChannelBadge(ADC_CH_LABELS[i], ADC_CH_COLORS[i])
            row.addWidget(badge, 1)
            self.badges.append(badge)
        outer.addLayout(row)

    def set_values(self, values: list):
        for badge, v in zip(self.badges, values):
            badge.set_value(int(v))


# --------------------------------------------------------------- rolling avg

class RollingAverage:
    """O(1)-per-sample ring-buffer moving average for one channel.

    Purely a GUI/display smoothing knob - independent of whatever the
    firmware itself does.
    """

    def __init__(self, window: int = 10):
        self.window = max(1, int(window))
        self.buf = deque(maxlen=self.window)
        self.sum = 0.0

    def update(self, value: float) -> float:
        if len(self.buf) == self.buf.maxlen:
            self.sum -= self.buf[0]
        self.buf.append(value)
        self.sum += value
        return self.sum / len(self.buf)


# --------------------------------------------------------------------- chart

class ADCChart(QFrame):
    """PyQtGraph live plot of the four ADC1 current channels (mA).

    The X axis is real time ("seconds ago", from host timestamps), so it stays
    correct whatever rate the firmware streams at.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GlassCard")
        self.setMinimumHeight(440)

        # history: one shared timestamp deque + one deque per channel
        self._t = deque(maxlen=HISTORY_SAMPLES)
        self.raw_series      = [deque(maxlen=HISTORY_SAMPLES) for _ in range(4)]
        self.smoothed_series = [deque(maxlen=HISTORY_SAMPLES) for _ in range(4)]

        self.ma_enabled = True
        self.ma_window = 3       # short: keeps the trace responsive
        self._ma = [RollingAverage(self.ma_window) for _ in range(4)]

        self._autoscale = True
        self._live = True
        self._span = DEFAULT_SPAN_S      # seconds; None = whole history
        self._paused = False
        self._t_ref = None               # frozen "now" while paused
        self._dirty = False

        self._build()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.start(REDRAW_MS)

    # ------------------------------------------------------------- UI

    @staticmethod
    def _btn(text, tip, checkable=False, checked=False):
        b = QPushButton(text)
        b.setStyleSheet(_BTN_QSS)
        b.setToolTip(tip)
        b.setCursor(Qt.PointingHandCursor)
        b.setCheckable(checkable)
        if checkable:
            b.setChecked(checked)
        return b

    @staticmethod
    def _muted(text):
        lbl = QLabel(text)
        lbl.setObjectName("Muted")
        lbl.setStyleSheet("background: transparent;")
        return lbl

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(8)

        # ---- row 1: data options ---------------------------------------
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        self.autoscale_btn = self._btn(
            "Autoscale: ON", "Fit the Y axis to the visible data",
            checkable=True, checked=True)
        self.autoscale_btn.toggled.connect(self._on_autoscale_toggled)
        row1.addWidget(self.autoscale_btn)

        self.ma_btn = self._btn(
            "Moving Avg: ON", "Extra display-only smoothing (host side)",
            checkable=True, checked=True)
        self.ma_btn.toggled.connect(self._on_ma_toggled)
        row1.addWidget(self.ma_btn)

        row1.addWidget(self._muted("Window"))
        self.ma_window_spin = QSpinBox()
        self.ma_window_spin.setRange(1, 200)
        self.ma_window_spin.setValue(self.ma_window)
        self.ma_window_spin.setFixedWidth(70)
        self.ma_window_spin.valueChanged.connect(self._on_ma_window_changed)
        row1.addWidget(self.ma_window_spin)

        row1.addStretch()

        self.pause_btn = self._btn(
            "Pause", "Freeze the picture (data keeps being buffered)",
            checkable=True)
        self.pause_btn.toggled.connect(self._on_pause_toggled)
        row1.addWidget(self.pause_btn)

        self.reset_btn = self._btn(
            "Reset view", "Live + Autoscale + 10 s span  (or double-click the plot)")
        self.reset_btn.clicked.connect(self._reset_view)
        row1.addWidget(self.reset_btn)

        outer.addLayout(row1)

        # ---- row 2: zoom / scale ---------------------------------------
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        row2.addWidget(self._muted("Y"))
        self.y_in_btn = self._btn("+", "Zoom in (Y)")
        self.y_in_btn.clicked.connect(lambda: self._zoom_y(0.5))
        row2.addWidget(self.y_in_btn)
        self.y_out_btn = self._btn("\u2212", "Zoom out (Y)")
        self.y_out_btn.clicked.connect(lambda: self._zoom_y(2.0))
        row2.addWidget(self.y_out_btn)

        row2.addWidget(self._muted("X"))
        self.x_in_btn = self._btn("+", "Zoom in (shorter time window)")
        self.x_in_btn.clicked.connect(lambda: self._zoom_x(0.5))
        row2.addWidget(self.x_in_btn)
        self.x_out_btn = self._btn("\u2212", "Zoom out (longer time window)")
        self.x_out_btn.clicked.connect(lambda: self._zoom_x(2.0))
        row2.addWidget(self.x_out_btn)

        row2.addWidget(self._muted("Span"))
        self.span_combo = QComboBox()
        self.span_combo.setStyleSheet(_COMBO_QSS)
        for label, _v in SPAN_PRESETS:
            self.span_combo.addItem(label)
        self._sync_span_combo()
        self.span_combo.currentIndexChanged.connect(self._on_span_changed)
        row2.addWidget(self.span_combo)

        self.live_btn = self._btn(
            "Live", "X axis follows the newest sample", checkable=True,
            checked=True)
        self.live_btn.toggled.connect(self._on_live_toggled)
        row2.addWidget(self.live_btn)

        row2.addStretch()

        row2.addWidget(self._muted("Y min"))
        self.ymin_spin = QDoubleSpinBox()
        self.ymin_spin.setRange(-1_000_000, 1_000_000)
        self.ymin_spin.setDecimals(1)
        self.ymin_spin.setSingleStep(10)
        self.ymin_spin.setKeyboardTracking(False)
        self.ymin_spin.setFixedWidth(92)
        self.ymin_spin.setValue(ADC_CURRENT_Y_MIN)
        self.ymin_spin.valueChanged.connect(self._on_spin_range)
        row2.addWidget(self.ymin_spin)

        row2.addWidget(self._muted("Y max"))
        self.ymax_spin = QDoubleSpinBox()
        self.ymax_spin.setRange(-1_000_000, 1_000_000)
        self.ymax_spin.setDecimals(1)
        self.ymax_spin.setSingleStep(10)
        self.ymax_spin.setKeyboardTracking(False)
        self.ymax_spin.setFixedWidth(92)
        self.ymax_spin.setValue(ADC_CURRENT_Y_MAX)
        self.ymax_spin.valueChanged.connect(self._on_spin_range)
        row2.addWidget(self.ymax_spin)

        outer.addLayout(row2)

        # ---- plot -------------------------------------------------------
        self.plot = pg.PlotWidget()
        self.vb = self.plot.getViewBox()
        self.vb.disableAutoRange()
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        # No "units=" on purpose: pyqtgraph would turn 20000 mA into "20 kmA".
        self.plot.setLabel("bottom", "Time (s ago)")
        self.plot.setLabel("left", "Current (mA)")
        for axis in ("left", "bottom"):
            self.plot.getAxis(axis).enableAutoSIPrefix(False)
        self.plot.setMouseEnabled(x=True, y=True)
        self.plot.addLegend(offset=(10, 6))

        # 0 mA reference line
        self.plot.addItem(pg.InfiniteLine(
            pos=0, angle=0, movable=False,
            pen=pg.mkPen((255, 255, 255, 70), width=1, style=Qt.DashLine)))

        self.curves = []
        for i in range(4):
            pen = pg.mkPen(color=ADC_CH_COLORS[i], width=2)
            curve = self.plot.plot([], [], pen=pen, name=ADC_CH_LABELS[i])
            curve.setClipToView(True)
            curve.setDownsampling(auto=True, method="peak")
            self.curves.append(curve)

        self.vb.setXRange(-self._span, 0.0, padding=0)
        self.vb.setYRange(-100.0, 100.0, padding=0)
        self._snap = self.vb.viewRange()

        self.vb.sigRangeChangedManually.connect(self._on_manual_range)
        self.vb.sigYRangeChanged.connect(lambda *_: self._sync_spins())
        self.plot.scene().sigMouseClicked.connect(self._on_scene_clicked)
        self.plot.scene().sigMouseMoved.connect(self._on_mouse_moved)

        outer.addWidget(self.plot, 1)

        # ---- footer: hint + cursor readout ------------------------------
        foot = QHBoxLayout()
        hint = self._muted(
            "wheel = zoom  \u00b7  drag = pan  \u00b7  right-drag = stretch axis"
            "  \u00b7  double-click = reset")
        foot.addWidget(hint)
        foot.addStretch()
        self.readout = QLabel("")
        self.readout.setObjectName("Muted")
        self.readout.setStyleSheet(
            f"color: {TEXT}; font-size: 12px; background: transparent;"
            f"font-family: 'JetBrains Mono', 'Consolas', monospace;")
        foot.addWidget(self.readout)
        outer.addLayout(foot)

    # ------------------------------------------------------------- data

    def push(self, values: list):
        self._t.append(time.monotonic())
        for i, v in enumerate(values[:4]):
            v = float(v)
            self.raw_series[i].append(v)
            self.smoothed_series[i].append(self._ma[i].update(v))
        self._dirty = True

    def _tick(self):
        if self._dirty and not self._paused:
            self._dirty = False
            self._redraw()

    def _arrays(self):
        """(x seconds-ago, [y0..y3]) for what should be on screen, or None."""
        n = len(self._t)
        if n == 0:
            return None
        t = np.fromiter(self._t, dtype=float, count=n)
        src = self.smoothed_series if self.ma_enabled else self.raw_series
        ys = [np.fromiter(s, dtype=float, count=n) for s in src]

        if self._paused and self._t_ref is not None:
            keep = t <= self._t_ref
            if not keep.any():
                return None
            t = t[keep]
            ys = [y[keep] for y in ys]
            t_ref = self._t_ref
        else:
            t_ref = t[-1]
        return t - t_ref, ys

    def _redraw(self):
        data = self._arrays()
        if data is None:
            return
        x, ys = data

        for curve, y in zip(self.curves, ys):
            curve.setData(x, y, skipFiniteCheck=True)

        x_range = None
        if self._live:
            x_lo = float(x[0]) if self._span is None else -self._span
            x_lo = min(x_lo, -0.5)
            x_range = (x_lo, 0.0)
            self._set_view(x=x_range)

        if self._autoscale:
            xlo = self.vb.viewRange()[0][0]
            sel = x >= xlo
            if not sel.any():
                sel = np.ones_like(x, dtype=bool)
            lo = min(float(y[sel].min()) for y in ys)
            hi = max(float(y[sel].max()) for y in ys)
            pad = max(10.0, (hi - lo) * 0.08)
            new_lo, new_hi = lo - pad, hi + pad
            # Hysteresis: only touch the Y range when the data leaves it or
            # it has become much looser than needed. Re-setting it every frame
            # makes pyqtgraph rebuild the axis ticks + grid ~60x/s, which is
            # the single most expensive thing in this redraw.
            cur_lo, cur_hi = self.vb.viewRange()[1]
            if (new_lo < cur_lo or new_hi > cur_hi
                    or (cur_hi - cur_lo) > 1.5 * (new_hi - new_lo)):
                self._set_view(y=(new_lo, new_hi))

    # ------------------------------------------------- view bookkeeping

    def _set_view(self, x=None, y=None):
        """Programmatic range change; refreshes the snapshot used to tell
        user interaction apart from our own updates."""
        if x is not None:
            self.vb.setXRange(x[0], x[1], padding=0)
        if y is not None:
            self.vb.setYRange(y[0], y[1], padding=0)
        self._snap = self.vb.viewRange()

    def _sync_spins(self):
        y0, y1 = self.vb.viewRange()[1]
        for spin, v in ((self.ymin_spin, y0), (self.ymax_spin, y1)):
            if spin.hasFocus():
                continue
            spin.blockSignals(True)
            spin.setValue(v)
            spin.blockSignals(False)

    def _sync_span_combo(self):
        idx = -1
        for i, (_label, v) in enumerate(SPAN_PRESETS):
            if v == self._span:
                idx = i
                break
        self.span_combo.blockSignals(True)
        self.span_combo.setCurrentIndex(idx)
        self.span_combo.blockSignals(False)

    def _set_autoscale(self, on: bool):
        self._autoscale = on
        self.autoscale_btn.blockSignals(True)
        self.autoscale_btn.setChecked(on)
        self.autoscale_btn.blockSignals(False)
        self.autoscale_btn.setText(f"Autoscale: {'ON' if on else 'OFF'}")

    def _set_live(self, on: bool):
        self._live = on
        self.live_btn.blockSignals(True)
        self.live_btn.setChecked(on)
        self.live_btn.blockSignals(False)

    # -------------------------------------------------------- user input

    def _on_manual_range(self, _mask):
        """Mouse pan/zoom. Work out which axis moved and release it from
        Live / Autoscale so the next redraw doesn't undo the user's move."""
        (x0, x1), (y0, y1) = self.vb.viewRange()
        (sx0, sx1), (sy0, sy1) = self._snap
        x_tol = 1e-6 * max(1.0, abs(sx1 - sx0))
        y_tol = 1e-6 * max(1.0, abs(sy1 - sy0))
        if abs(x0 - sx0) > x_tol or abs(x1 - sx1) > x_tol:
            self._set_live(False)
        if abs(y0 - sy0) > y_tol or abs(y1 - sy1) > y_tol:
            self._set_autoscale(False)
        self._snap = self.vb.viewRange()
        self._sync_spins()

    def _on_scene_clicked(self, ev):
        if ev.double() and self.vb.sceneBoundingRect().contains(ev.scenePos()):
            self._reset_view()

    def _on_mouse_moved(self, pos):
        if self.vb.sceneBoundingRect().contains(pos):
            p = self.vb.mapSceneToView(pos)
            self.readout.setText(f"t {p.x():+7.2f} s    I {p.y():+9.1f} mA")
        else:
            self.readout.setText("")

    def _zoom_y(self, factor: float):
        y0, y1 = self.vb.viewRange()[1]
        c = 0.5 * (y0 + y1)
        h = max(0.5 * (y1 - y0) * factor, 0.5 * MIN_Y_SPAN)
        self._set_autoscale(False)
        self._set_view(y=(c - h, c + h))

    def _zoom_x(self, factor: float):
        x0, x1 = self.vb.viewRange()[0]
        if self._live:
            cur = self._span if self._span is not None else -x0
            self._span = min(max(cur * factor, 0.5), 3600.0)
            self._sync_span_combo()
            self._redraw()
        else:
            c = 0.5 * (x0 + x1)
            h = max(0.5 * (x1 - x0) * factor, 0.25)
            self._set_view(x=(c - h, c + h))

    def _on_span_changed(self, idx: int):
        if idx < 0:
            return
        self._span = SPAN_PRESETS[idx][1]
        self._set_live(True)
        self._redraw()

    def _on_live_toggled(self, on: bool):
        self._live = on
        if on:
            self._redraw()

    def _on_autoscale_toggled(self, on: bool):
        self._autoscale = on
        self.autoscale_btn.setText(f"Autoscale: {'ON' if on else 'OFF'}")
        if on:
            self._redraw()

    def _on_spin_range(self, _value):
        lo, hi = self.ymin_spin.value(), self.ymax_spin.value()
        if hi - lo < MIN_Y_SPAN:
            return
        self._set_autoscale(False)
        self._set_view(y=(lo, hi))

    def _on_pause_toggled(self, on: bool):
        self._paused = on
        self.pause_btn.setText("Resume" if on else "Pause")
        if on:
            self._t_ref = self._t[-1] if self._t else None
        else:
            self._t_ref = None
            self._redraw()

    def _reset_view(self):
        self._span = DEFAULT_SPAN_S
        self._sync_span_combo()
        self._set_autoscale(True)
        self._set_live(True)
        if self._t:
            self._redraw()
        else:
            self._set_view(x=(-self._span, 0.0), y=(-100.0, 100.0))

    # ---------------------------------------------------- smoothing knobs

    def _on_ma_toggled(self, on: bool):
        self.ma_enabled = on
        self.ma_btn.setText(f"Moving Avg: {'ON' if on else 'OFF'}")
        self.ma_window_spin.setEnabled(on)
        self._redraw()

    def _on_ma_window_changed(self, value: int):
        window = max(1, int(value))
        self.ma_window = window
        for i in range(4):
            ra = RollingAverage(window)
            smoothed = deque(maxlen=HISTORY_SAMPLES)
            for v in self.raw_series[i]:
                smoothed.append(ra.update(v))
            self._ma[i] = ra
            self.smoothed_series[i] = smoothed
        self._redraw()


# --------------------------------------------------------------------- host

class MonitoringWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        heading = QLabel("LIVE SYSTEM MONITORING")
        heading.setObjectName("Heading")
        layout.addWidget(heading)

        self.summary = SummaryRow()
        layout.addWidget(self.summary)

        self.chart = ADCChart()
        layout.addWidget(self.chart, 1)

        self._last_badge = 0.0

    def push_adc1(self, counts: list):
        now = time.monotonic()
        if now - self._last_badge >= BADGE_MIN_INTERVAL_S:
            self._last_badge = now
            self.summary.set_values(counts)
        self.chart.push(counts)