"""Application stylesheet."""

APP_STYLESHEET = """
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
