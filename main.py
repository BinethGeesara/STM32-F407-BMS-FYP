"""Application entry point."""
import sys

from PyQt5.QtWidgets import QApplication

from dashboard import MainWindow
from theme import app_stylesheet


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(app_stylesheet())

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()