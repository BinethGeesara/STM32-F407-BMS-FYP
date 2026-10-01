"""Connection panel: status dot + pill buttons."""
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)
from PyQt5.QtCore import Qt, pyqtSignal

from theme import (
    ACCENT, BORDER, ERROR, PANEL_GLASS, SUCCESS, TEXT, TEXT_MUTED, WARNING,
)


class StatusDot(QWidget):
    """Small glowing circle drawn via QSS."""

    def __init__(self, color: str = TEXT_MUTED, parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(12, 12)

    def set_color(self, color: str):
        self._color = color
        self.update()

    def paintEvent(self, event):
        from PyQt5.QtGui import QPainter, QColor, QBrush, QRadialGradient
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # glow
        grad = QRadialGradient(6, 6, 8)
        c = QColor(self._color)
        c.setAlpha(110)
        grad.setColorAt(0.0, c)
        c.setAlpha(0)
        grad.setColorAt(1.0, c)
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, 12, 12)
        # core
        p.setBrush(QColor(self._color))
        p.drawEllipse(3, 3, 6, 6)


class ConnectionWidget(QFrame):
    connect_clicked         = pyqtSignal()
    auto_reconnect_toggled  = pyqtSignal(bool)
    sync_clicked            = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GlassCard")
        self._connected = False
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(6)

        heading = QLabel("CONNECTION")
        heading.setObjectName("Heading")
        outer.addWidget(heading)

        row = QHBoxLayout()
        row.setSpacing(10)

        self.dot = StatusDot(ERROR)
        row.addWidget(self.dot)

        self.status_label = QLabel("Disconnected")
        self.status_label.setObjectName("Body")
        row.addWidget(self.status_label, 1)

        self.sync_btn = QPushButton("Read State")
        self.sync_btn.setObjectName("Pill")
        self.sync_btn.clicked.connect(self.sync_clicked.emit)
        self.sync_btn.setEnabled(False)
        row.addWidget(self.sync_btn)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("Pill")
        self.connect_btn.clicked.connect(self.connect_clicked.emit)
        row.addWidget(self.connect_btn)

        outer.addLayout(row)

        self.detail_label = QLabel("")
        self.detail_label.setObjectName("Muted")
        outer.addWidget(self.detail_label)

    # -- public -------------------------------------------------------------

    def set_connected(self, connected: bool, message: str = ""):
        self._connected = connected
        self.dot.set_color(SUCCESS if connected else ERROR)
        self.status_label.setText(message or ("Connected" if connected else "Disconnected"))
        self.connect_btn.setText("Disconnect" if connected else "Connect")
        self.sync_btn.setEnabled(connected)
        if connected:
            self.detail_label.setText("")

    def set_reconnect_attempt(self, attempt: int):
        self.detail_label.setText(f"Reconnect attempt {attempt}")

    def set_detail(self, text: str):
        self.detail_label.setText(text)

    def is_connected(self) -> bool:
        return self._connected