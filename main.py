"""Application entry point for the CNC Lathe Simulator."""

import sys

from PyQt6.QtWidgets import QApplication

from cnc_sim.main_window import MainWindow
from cnc_sim.styles import APP_STYLESHEET


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("CNC Lathe Simulator")
    app.setOrganizationName("CIMtech")
    app.setStyleSheet(APP_STYLESHEET)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
