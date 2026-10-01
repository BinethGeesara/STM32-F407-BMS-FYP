"""Cell Balancing tab: Start / Stop automatic balancing.

This widget is only the face of the feature. It emits start_clicked /
stop_clicked; the command sequencing lives in dashboard.py, which tells the
widget what phase it is in via set_phase().

Phases:  idle -> starting -> running -> stopping -> idle
"""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from config import (
    BALANCE_PWM_DUTY, BALANCE_PWM_FREQ_HZ, BALANCE_SWITCHES, BALANCE_TITLE,
)
from theme import ACCENT, BORDER, ERROR, INNER_DARK, PANEL, TEXT, TEXT_DIM, TEXT_MUTED

_START_QSS = f"""
    QPushButton {{
        background: {ACCENT}; color: #05080B; border: 1px solid {ACCENT};
        border-radius: 999px; padding: 9px 20px;
        font-size: 12px; font-weight: 700;
    }}
    QPushButton:disabled {{
        background: {INNER_DARK}; color: {TEXT_DIM}; border-color: {BORDER};
    }}
"""

_STOP_QSS = f"""
    QPushButton {{
        background: {INNER_DARK}; color: {ERROR}; border: 1px solid {ERROR};
        border-radius: 999px; padding: 9px 20px;
        font-size: 12px; font-weight: 700;
    }}
    QPushButton:hover {{ background: #2A1518; }}
    QPushButton:disabled {{ color: {TEXT_DIM}; border-color: {BORDER};
                            background: {INNER_DARK}; }}
"""


def _label(text="", style=""):
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(f"background: transparent; {style}")
    return lbl


class BalancingWidget(QFrame):
    start_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GlassCard")
        self._phase = "idle"
        self._link_ready = False
        self._build()
        self._refresh()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        heading = _label("AUTOMATIC BALANCING")
        heading.setObjectName("Heading")
        layout.addWidget(heading)

        # ---- buttons ---------------------------------------------------
        row = QHBoxLayout()
        row.setSpacing(10)
        self.start_btn = QPushButton("Start Automatic Balancing")
        self.start_btn.setStyleSheet(_START_QSS)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self.start_clicked.emit)
        row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop Automatic Balancing")
        self.stop_btn.setStyleSheet(_STOP_QSS)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.clicked.connect(self.stop_clicked.emit)
        row.addWidget(self.stop_btn)
        row.addStretch()
        layout.addLayout(row)

        self.status_lbl = _label("Idle", f"color: {TEXT_MUTED}; font-size: 12px;")
        layout.addWidget(self.status_lbl)

        # ---- shown while balancing -------------------------------------
        self.active_box = QFrame()
        self.active_box.setObjectName("BalanceActive")
        self.active_box.setStyleSheet(
            f"QFrame#BalanceActive {{ background: {PANEL};"
            f" border: 1px solid {BORDER}; border-radius: 12px; }}"
        )
        box = QVBoxLayout(self.active_box)
        box.setContentsMargins(16, 14, 16, 14)
        box.setSpacing(8)

        box.addWidget(_label(
            BALANCE_TITLE,
            f"color: {TEXT}; font-size: 20px; font-weight: 700;"
            f" letter-spacing: 0.5px;"))

        sw = ",  ".join(f"Cell {c} {t}" for c, t in BALANCE_SWITCHES)
        box.addWidget(_label(f"Switches ON:  {sw}",
                             f"color: {TEXT_MUTED}; font-size: 12px;"))

        duties = ",  ".join(f"CH{ch} {d}%" for ch, d in sorted(BALANCE_PWM_DUTY.items()))
        box.addWidget(_label(
            f"PWM ON:  {BALANCE_PWM_FREQ_HZ / 1000:g} kHz   ({duties})",
            f"color: {TEXT_MUTED}; font-size: 12px;"))

        box.addWidget(_label(
            "All other switches are OFF. The Cells and PWM Control tabs are "
            "locked until you press Stop.",
            f"color: {TEXT_DIM}; font-size: 11px;"))
        layout.addWidget(self.active_box)

        layout.addStretch(1)

    # ------------------------------------------------------------ public

    def set_phase(self, phase: str):
        self._phase = phase
        self._refresh()

    def set_link_ready(self, ready: bool):
        self._link_ready = ready
        self._refresh()

    def set_status(self, text: str, color: str = TEXT_MUTED):
        self.status_lbl.setText(text)
        self.status_lbl.setStyleSheet(
            f"background: transparent; color: {color}; font-size: 12px;")

    # ---------------------------------------------------------- internals

    def _refresh(self):
        active = self._phase in ("starting", "running")
        self.active_box.setVisible(active)
        self.start_btn.setEnabled(self._link_ready and self._phase == "idle")
        self.stop_btn.setEnabled(self._link_ready and active)