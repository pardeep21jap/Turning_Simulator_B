"""Application stylesheets."""

DARK_STYLESHEET = """
QMainWindow, QWidget { background: #10161f; color: #dce8f2; font-family: 'Segoe UI'; font-size: 10pt; }
QMenuBar, QMenu { background: #17212c; color: #dce8f2; }
QToolBar { background: #17212c; border-bottom: 1px solid #2b3a49; spacing: 6px; padding: 6px; }
QPushButton, QToolButton, QComboBox, QDoubleSpinBox, QSpinBox {
  background: #223141; border: 1px solid #3b5268; border-radius: 5px; padding: 6px 10px; color: #e9f2f9;
}
QPushButton:hover, QToolButton:hover { background: #2e4559; border-color: #5fbce8; }
QPushButton:pressed, QToolButton:pressed { background: #172431; }
QPushButton#startButton { background: #137a55; border-color: #24b27e; font-weight: 600; }
QPushButton#pauseButton { background: #8b5c14; border-color: #d59a37; }
QPlainTextEdit { background: #0b1118; color: #d6e3ec; border: 1px solid #2b3d4c; font-family: Consolas; font-size: 10pt; selection-background-color: #235a75; }
QTableWidget { background: #0c131b; alternate-background-color: #121d27; gridline-color: #263745; border: 1px solid #2b3d4c; }
QHeaderView::section { background: #1d2a37; color: #bed0dd; padding: 5px; border: none; border-right: 1px solid #314354; }
QTabWidget::pane { border: 1px solid #2b3d4c; }
QTabBar::tab { background: #19242f; padding: 8px 14px; }
QTabBar::tab:selected { background: #264158; color: #77d3ff; }
QLabel#statusReadout { background: #0a1118; border: 1px solid #2c4050; border-radius: 4px; padding: 6px; font-family: Consolas; color: #8ee6b8; }
QStatusBar { background: #17212c; color: #9db0bf; }
QSplitter::handle { background: #2b3d4c; width: 3px; }
"""

LIGHT_STYLESHEET = """
QMainWindow, QWidget { background: #eef2f6; color: #1f2933; font-family: 'Segoe UI'; font-size: 10pt; }
QMenuBar, QMenu { background: #ffffff; color: #1f2933; }
QToolBar { background: #ffffff; border-bottom: 1px solid #c9d3dc; spacing: 6px; padding: 6px; }
QPushButton, QToolButton, QComboBox, QDoubleSpinBox, QSpinBox {
  background: #ffffff; border: 1px solid #b7c3cf; border-radius: 5px; padding: 6px 10px; color: #1f2933;
}
QPushButton:hover, QToolButton:hover { background: #e3edf5; border-color: #3d8fc4; }
QPushButton:pressed, QToolButton:pressed { background: #d3e2ec; }
QPushButton#startButton { background: #1f9c6e; border-color: #157a54; color: #ffffff; font-weight: 600; }
QPushButton#pauseButton { background: #d59a37; border-color: #a9741d; color: #ffffff; }
QPlainTextEdit { background: #ffffff; color: #1f2933; border: 1px solid #c9d3dc; font-family: Consolas; font-size: 10pt; selection-background-color: #bfe0f5; }
QTableWidget { background: #ffffff; alternate-background-color: #eef3f7; gridline-color: #d7e0e8; border: 1px solid #c9d3dc; color: #1f2933; }
QHeaderView::section { background: #e3eaf0; color: #33424f; padding: 5px; border: none; border-right: 1px solid #c9d3dc; }
QTabWidget::pane { border: 1px solid #c9d3dc; }
QTabBar::tab { background: #e3eaf0; color: #33424f; padding: 8px 14px; }
QTabBar::tab:selected { background: #ffffff; color: #0f6fa3; }
QLabel#statusReadout { background: #ffffff; border: 1px solid #c9d3dc; border-radius: 4px; padding: 6px; font-family: Consolas; color: #157a54; }
QStatusBar { background: #ffffff; color: #4b5b68; }
QSplitter::handle { background: #c9d3dc; width: 3px; }
"""

APP_STYLESHEET = DARK_STYLESHEET
