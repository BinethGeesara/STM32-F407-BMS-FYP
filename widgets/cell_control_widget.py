"""Cell cards - premium glass cards with a battery-shaped hero readout."""
from PyQt5.QtWidgets import (
    QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout, QWidget, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from config import (
    CELL_COLORS, CELL_COUNT, SWITCH_LABELS, SWITCH_TYPES,
)
from theme import (
    BORDER, ERROR, PANEL, PANEL_GLASS, SUCCESS, TEXT, TEXT_MUTED,
    TEXT_DIM, ACCENT, toggle_switch_qss,
)


def _mv_html(text: str) -> str:
    """Big number followed by a small muted unit, all in one QLabel."""
    return (f'{text}<span style="font-size:15px; font-weight:600;'
            f' color:{TEXT_MUTED};"> mV</span>')


# ----------------------------------------------------------------- toggles

class ToggleRow(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, label: str, accent: str, parent=None):
        super().__init__(parent)
        self._accent = accent
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 1, 0, 1)
        row.setSpacing(8)

        self.label = QLabel(label)
        self.label.setObjectName("Body")
        row.addWidget(self.label, 1)

        self.toggle = QCheckBox()
        self.toggle.setStyleSheet(toggle_switch_qss(accent))
        self.toggle.setCursor(Qt.PointingHandCursor)
        self.toggle.toggled.connect(self.toggled.emit)
        row.addWidget(self.toggle, 0, Qt.AlignRight)

    def set_state(self, on: bool, pending: bool = False):
        self.toggle.blockSignals(True)
        self.toggle.setChecked(on)
        self.toggle.blockSignals(False)

    def is_on(self) -> bool:
        return self.toggle.isChecked()

    def set_enabled(self, enabled: bool):
        self.toggle.setEnabled(enabled)
        self.label.setEnabled(enabled)


# -------------------------------------------------------------------- card

class CellCard(QFrame):
    switch_toggled = pyqtSignal(int, str, bool)

    def __init__(self, cell_num: int, accent: str, parent=None):
        super().__init__(parent)
        self.setObjectName("GlassCard")
        self.cell_num = cell_num
        self.accent = accent
        self.switch_rows = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # ---- header ---------------------------------------------------
        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel(f"CELL {self.cell_num}")
        title.setObjectName("Title")
        header.addWidget(title)
        header.addStretch()

        dot = QLabel("●")
        dot.setStyleSheet(f"color: {self.accent}; font-size: 16px;")
        header.addWidget(dot)

        layout.addLayout(header)

        # ---- readout panel (static, no dynamic painting) --------------
        readout = QFrame()
        readout.setStyleSheet(
            f"QFrame {{ background: {PANEL}; border: 1px solid {BORDER};"
            f" border-radius: 12px; }}"
        )
        readout.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        g = QVBoxLayout(readout)
        g.setContentsMargins(14, 12, 14, 12)
        g.setSpacing(1)

        # ---- VOLTAGE block -------------------------------------------
        v_cap = QLabel("VOLTAGE")
        v_cap.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 8px;"
            f"font-weight: 700; letter-spacing: 1px;"
        )
        v_cap.setAlignment(Qt.AlignCenter)
        g.addWidget(v_cap)

        self.voltage_lbl = QLabel(_mv_html("----"))
        fv = QFont()
        fv.setPointSize(32)
        fv.setWeight(QFont.Bold)
        fv.setFamily("JetBrains Mono")
        self.voltage_lbl.setFont(fv)
        self.voltage_lbl.setStyleSheet(
            f"color: {TEXT}; background: transparent;"
            f"font-size: 32px; font-weight: 700;"
            f"font-family: 'JetBrains Mono', 'Consolas', monospace;"
        )
        self.voltage_lbl.setAlignment(Qt.AlignCenter)
        g.addWidget(self.voltage_lbl)

        # ---- divider --------------------------------------------------
        g.addSpacing(2)
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {BORDER};")
        g.addWidget(div)
        g.addSpacing(2)

        # ---- TEMP block ----------------------------------------------
        t_cap = QLabel("TEMP")
        t_cap.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 8px;"
            f"font-weight: 700; letter-spacing: 1px;"
        )
        t_cap.setAlignment(Qt.AlignCenter)
        g.addWidget(t_cap)

        self.temp_lbl = QLabel("--")
        ft = QFont()
        ft.setPointSize(26)
        ft.setWeight(QFont.Bold)
        ft.setFamily("JetBrains Mono")
        self.temp_lbl.setFont(ft)
        self.temp_lbl.setStyleSheet(
            f"color: #FBBF24; background: transparent;"
            f"font-size: 26px; font-weight: 700;"
            f"font-family: 'JetBrains Mono', 'Consolas', monospace;"
        )
        self.temp_lbl.setAlignment(Qt.AlignCenter)
        g.addWidget(self.temp_lbl)

        g.addStretch(1)

        layout.addWidget(readout, 1)

        # ---- toggles --------------------------------------------------
        toggles_box = QFrame()
        toggles_box.setStyleSheet(
            f"QFrame {{ background: {PANEL}; border: 1px solid {BORDER};"
            f" border-radius: 12px; }}"
        )
        toggles_layout = QVBoxLayout(toggles_box)
        toggles_layout.setContentsMargins(8, 2, 8, 2)
        toggles_layout.setSpacing(0)

        for sw in SWITCH_TYPES:
            row = ToggleRow(SWITCH_LABELS[sw], self.accent)
            row.toggled.connect(
                lambda on, t=sw: self.switch_toggled.emit(self.cell_num, t, on)
            )
            toggles_layout.addWidget(row)
            self.switch_rows[sw] = row

        layout.addWidget(toggles_box, 0)

    # ---- public ------------------------------------------------------

    def apply_state(self, cell_state: dict):
        for sw, row in self.switch_rows.items():
            row.set_state(bool(cell_state.get(sw, False)), pending=False)

    def apply_voltage(self, millivolts: float):
        mv = int(millivolts)
        self.voltage_lbl.setText(_mv_html(str(mv)))

    def apply_temperature(self, value: float):
        self.temp_lbl.setText(f"{int(round(value))} \u00B0C")

    def set_enabled(self, enabled: bool):
        for row in self.switch_rows.values():
            row.set_enabled(enabled)


# --------------------------------------------------------------- container

class CellControlWidget(QFrame):
    """2-column grid of cell cards (scrollable host adds it)."""

    switch_command  = pyqtSignal(int, str, bool)
    all_off_command = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GlassCard")
        self.cells = {}
        self._build()
        self.set_enabled(False)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        grid = QGridLayout()
        grid.setSpacing(6)
        for i in range(CELL_COUNT):
            n = i + 1
            card = CellCard(n, CELL_COLORS[i % len(CELL_COLORS)])
            card.switch_toggled.connect(self.switch_command.emit)
            grid.addWidget(card, i // 2, i % 2)
            self.cells[n] = card

        layout.addLayout(grid)

        self.all_off_btn = QPushButton("All Cells Off")
        self.all_off_btn.setObjectName("Pill")
        self.all_off_btn.clicked.connect(self.all_off_command.emit)
        layout.addWidget(self.all_off_btn)

    # ---- public ------------------------------------------------------

    def apply_states(self, states: dict):
        for cell, card in self.cells.items():
            if cell in states:
                card.apply_state(states[cell])

    def apply_cell_voltages(self, volts: list):
        for i, v in enumerate(volts):
            if (i + 1) in self.cells:
                self.cells[i + 1].apply_voltage(v)

    def apply_cell_temperatures(self, temps: list):
        for i, t in enumerate(temps):
            if (i + 1) in self.cells:
                self.cells[i + 1].apply_temperature(t)

    def set_enabled(self, enabled: bool):
        for card in self.cells.values():
            card.set_enabled(enabled)
        self.all_off_btn.setEnabled(enabled)