"""Console: raw command line + scrolling log.

Lines are buffered and written to the document in one batch every
FLUSH_MS, instead of one appendHtml() per line. Streaming telemetry
(ADC:/TEMP:/BQ_*) is hidden by default; tick the box to see it.
"""
from collections import deque

from PyQt5.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QVBoxLayout,
)
from PyQt5.QtGui import QFont, QTextCursor
from PyQt5.QtCore import QTimer, pyqtSignal

from theme import (
    ACCENT, ERROR, FONT_MONO, INNER_DARK, TEXT, WARNING,
)

FLUSH_MS = 100
MAX_PENDING = 500          # drop the oldest if the GUI can't keep up
TELEMETRY_PREFIXES = (
    "ADC:", "TEMP:", "BQ_CELLS:", "BQ_STACK:", "BQ_SUMCELLS:", "BQ_BATTSTAT:",
)


class ConsoleWidget(QFrame):
    command_sent = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GlassCard")
        self._pending = deque(maxlen=MAX_PENDING)
        self._show_telemetry = False
        self._build()

        self._flush_timer = QTimer(self)
        self._flush_timer.timeout.connect(self._flush)
        self._flush_timer.start(FLUSH_MS)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        head = QHBoxLayout()
        heading = QLabel("CONSOLE")
        heading.setObjectName("Heading")
        head.addWidget(heading)
        head.addStretch()
        self.telemetry_chk = QCheckBox("Show telemetry lines")
        self.telemetry_chk.setStyleSheet("background: transparent;")
        self.telemetry_chk.toggled.connect(self._on_telemetry_toggled)
        head.addWidget(self.telemetry_chk)
        layout.addLayout(head)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(2000)
        self.output.setFont(QFont(FONT_MONO.split(",")[0].strip("'"), 9))
        self.output.setStyleSheet(
            f"QPlainTextEdit {{ background: {INNER_DARK}; color: {TEXT};"
            f"border: 1px solid rgba(255,255,255,0.05); border-radius: 8px;"
            f"padding: 8px; }}"
        )
        layout.addWidget(self.output, 1)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a command and press Enter  (try  ?  or  Q )")
        self.input.setFont(QFont(FONT_MONO.split(",")[0].strip("'"), 9))
        self.input.returnPressed.connect(self._submit)
        layout.addWidget(self.input)

    def _on_telemetry_toggled(self, on: bool):
        self._show_telemetry = on

    def _submit(self):
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.command_sent.emit(text)

    # -- display -------------------------------------------------------

    def append_command(self, text: str):
        self._queue(f"> {text}", ACCENT)

    def append_response(self, text: str):
        if not self._show_telemetry and text.startswith(TELEMETRY_PREFIXES):
            return
        self._queue(text, TEXT)

    def append_note(self, text: str):
        self._queue(f"* {text}", WARNING)

    def append_error(self, text: str):
        self._queue(f"! {text}", ERROR)

    def _queue(self, text: str, color: str):
        self._pending.append((text, color))

    def _flush(self):
        if not self._pending:
            return
        items = list(self._pending)
        self._pending.clear()
        parts = []
        for text, color in items:
            safe = (text.replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;"))
            parts.append(
                f'<div style="color:{color};white-space:pre-wrap;">{safe}</div>'
            )
        self.output.appendHtml("".join(parts))
        self.output.moveCursor(QTextCursor.End)
        self.output.ensureCursorVisible()

    def set_input_enabled(self, enabled: bool):
        self.input.setEnabled(enabled)
        if enabled:
            self.input.setFocus()