"""PWM tab: frequency + 4 channel sliders + apply-all."""
from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QSpinBox, QVBoxLayout,
)
from PyQt5.QtCore import Qt, pyqtSignal

from theme import ACCENT, BG, BORDER, INNER_DARK, TEXT, TEXT_MUTED


class PWMControlWidget(QFrame):
    pwm_command = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GlassCard")
        self._pwm_on = False
        self._build()
        self.set_enabled(False)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        heading = QLabel("TIM1 PWM")
        heading.setObjectName("Heading")
        layout.addWidget(heading)

        # --- enable button ---------------------------------------------
        self.enable_btn = QPushButton("PWM: OFF")
        self.enable_btn.setObjectName("Pill")
        self.enable_btn.setCheckable(True)
        self.enable_btn.setFixedHeight(40)
        self.enable_btn.setStyleSheet(f"""
            QPushButton {{
                background: {INNER_DARK}; color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 20px; font-weight: 600; font-size: 13px;
            }}
            QPushButton:checked {{
                background: {ACCENT}; color: #000; border-color: {ACCENT};
            }}
        """)
        self.enable_btn.toggled.connect(self._on_enable)
        layout.addWidget(self.enable_btn)

        # --- frequency -------------------------------------------------
        freq_row = QHBoxLayout()
        freq_row.addWidget(QLabel("Frequency (Hz)"))
        self.freq_spin = QSpinBox()
        self.freq_spin.setRange(100, 168000)
        self.freq_spin.setSingleStep(1000)
        self.freq_spin.setValue(71000)
        freq_row.addWidget(self.freq_spin, 1)
        self.freq_btn = QPushButton("Set")
        self.freq_btn.setObjectName("Pill")
        self.freq_btn.clicked.connect(
            lambda: self.pwm_command.emit(f"F{self.freq_spin.value()}")
        )
        freq_row.addWidget(self.freq_btn)
        layout.addLayout(freq_row)

        # --- channels --------------------------------------------------
        grid = QGridLayout()
        grid.setSpacing(8)
        self.duty_sliders = {}
        for ch in range(1, 5):
            grid.addWidget(QLabel(f"CH{ch}"), ch - 1, 0)
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(40 if ch == 4 else 0)
            slider.sliderReleased.connect(
                lambda c=ch: self.pwm_command.emit(f"D{c}={self.duty_sliders[c].value()}")
            )
            grid.addWidget(slider, ch - 1, 1)
            val = QLabel(f"{slider.value()}%")
            val.setFixedWidth(40)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            slider.valueChanged.connect(lambda v, l=val: l.setText(f"{v}%"))
            grid.addWidget(val, ch - 1, 2)
            self.duty_sliders[ch] = slider

        layout.addLayout(grid)

        self.apply_all = QPushButton("Apply All Duties")
        self.apply_all.setObjectName("Pill")
        self.apply_all.clicked.connect(self._apply_all)
        layout.addWidget(self.apply_all)

        layout.addStretch()

    # ---------------------------------------------------------------

    def _on_enable(self, on: bool):
        self._pwm_on = on
        self.enable_btn.setText(f"PWM: {'ON' if on else 'OFF'}")
        self.pwm_command.emit(f"P={1 if on else 0}")

    def _apply_all(self):
        for ch in range(1, 5):
            self.pwm_command.emit(f"D{ch}={self.duty_sliders[ch].value()}")

    def apply_external(self, on: bool, freq=None, duties=None):
        """Show a state that was set from elsewhere (e.g. auto balancing).

        Updates the widgets only - no command is emitted.
        """
        self._pwm_on = on
        self.enable_btn.blockSignals(True)
        self.enable_btn.setChecked(on)
        self.enable_btn.blockSignals(False)
        self.enable_btn.setText(f"PWM: {'ON' if on else 'OFF'}")
        if freq is not None:
            self.freq_spin.setValue(int(freq))
        if duties:
            for ch, duty in duties.items():
                if ch in self.duty_sliders:
                    self.duty_sliders[ch].setValue(int(duty))

    def set_enabled(self, enabled: bool):
        self.enable_btn.setEnabled(enabled)
        self.freq_spin.setEnabled(enabled)
        self.freq_btn.setEnabled(enabled)
        self.apply_all.setEnabled(enabled)
        for s in self.duty_sliders.values():
            s.setEnabled(enabled)