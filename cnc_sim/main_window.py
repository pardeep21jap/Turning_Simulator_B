"""Main PyQt6 desktop interface."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QKeySequence, QTextCharFormat, QTextCursor, QTextFormat
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .canvas import LatheCanvas
from .examples import EXAMPLES
from .parser import FanucParser
from .simulation import SimulationEngine


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CNC Lathe Simulator — FANUC Training")
        self.resize(1440, 850)
        self.parser = FanucParser()
        self.engine = SimulationEngine()
        self.engine.line_changed.connect(self._highlight_line)
        self.engine.changed.connect(self._update_readout)
        self.engine.finished.connect(lambda: self.statusBar().showMessage("Program complete", 5000))
        self._build_ui()
        self._load_example(next(iter(EXAMPLES)))

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(8, 8, 8, 4)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Program"))
        self.examples = QComboBox()
        self.examples.addItems(EXAMPLES.keys())
        self.examples.currentTextChanged.connect(self._load_example)
        controls.addWidget(self.examples)
        controls.addWidget(QLabel("Stock Ø"))
        self.stock_diameter = QDoubleSpinBox()
        self.stock_diameter.setRange(5.0, 300.0)
        self.stock_diameter.setValue(50.0)
        self.stock_diameter.setSuffix(" mm")
        controls.addWidget(self.stock_diameter)
        controls.addWidget(QLabel("Length"))
        self.stock_length = QDoubleSpinBox()
        self.stock_length.setRange(10.0, 500.0)
        self.stock_length.setValue(100.0)
        self.stock_length.setSuffix(" mm")
        controls.addWidget(self.stock_length)
        parse_button = QPushButton("Parse / Reset")
        parse_button.clicked.connect(self.parse_program)
        controls.addWidget(parse_button)
        self.start_button = QPushButton("Cycle Start")
        self.start_button.setObjectName("startButton")
        self.start_button.clicked.connect(self.engine.play)
        controls.addWidget(self.start_button)
        pause_button = QPushButton("Pause")
        pause_button.setObjectName("pauseButton")
        pause_button.clicked.connect(self.engine.pause)
        controls.addWidget(pause_button)
        step_button = QPushButton("Single Block")
        step_button.clicked.connect(self.engine.single_block)
        controls.addWidget(step_button)
        controls.addWidget(QLabel("Speed"))
        speed = QDoubleSpinBox()
        speed.setRange(0.1, 10.0)
        speed.setSingleStep(0.25)
        speed.setValue(1.0)
        speed.setSuffix("×")
        speed.valueChanged.connect(self.engine.set_speed)
        controls.addWidget(speed)
        controls.addStretch(1)
        self.readout = QLabel("X --  Z --  F --  S --")
        self.readout.setObjectName("statusReadout")
        controls.addWidget(self.readout)
        root_layout.addLayout(controls)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.editor = QPlainTextEdit()
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.editor.setMinimumWidth(340)
        splitter.addWidget(self.editor)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        view_controls = QHBoxLayout()
        machine_button = QPushButton("Machine View")
        drawing_button = QPushButton("Drawing View")
        machine_button.clicked.connect(lambda: self.canvas.set_mode("machine"))
        drawing_button.clicked.connect(lambda: self.canvas.set_mode("drawing"))
        view_controls.addWidget(machine_button)
        view_controls.addWidget(drawing_button)
        view_controls.addStretch(1)
        center_layout.addLayout(view_controls)
        self.canvas = LatheCanvas(self.engine)
        center_layout.addWidget(self.canvas, 1)
        splitter.addWidget(center)

        self.tabs = QTabWidget()
        self.tabs.setMinimumWidth(310)
        self.motion_table = QTableWidget(0, 5)
        self.motion_table.setHorizontalHeaderLabels(["Line", "Mode", "X", "Z", "Cycle"])
        self.motion_table.setAlternatingRowColors(True)
        self.motion_table.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.motion_table, "Toolpath")
        self.alarm_table = QTableWidget(0, 3)
        self.alarm_table.setHorizontalHeaderLabels(["Line", "Code", "Message"])
        self.alarm_table.setAlternatingRowColors(True)
        self.alarm_table.horizontalHeader().setStretchLastSection(True)
        self.alarm_table.cellDoubleClicked.connect(self._go_to_alarm)
        self.tabs.addTab(self.alarm_table, "Alarms")
        splitter.addWidget(self.tabs)
        splitter.setSizes([370, 760, 310])
        root_layout.addWidget(splitter, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage("Educational simulator — not for production verification")
        self.editor.document().modificationChanged.connect(self._edited)
        self.editor.setUndoRedoEnabled(True)
        parse_action = QAction("Parse program", self)
        parse_action.setShortcut(QKeySequence("F5"))
        parse_action.triggered.connect(self.parse_program)
        self.addAction(parse_action)

    def _load_example(self, name: str) -> None:
        if name not in EXAMPLES:
            return
        self.editor.setPlainText(EXAMPLES[name])
        self.editor.document().setModified(False)
        self.parse_program()

    def _edited(self, changed: bool) -> None:
        if changed:
            self.statusBar().showMessage("Program edited — select Parse / Reset before running")

    def parse_program(self) -> None:
        program = self.parser.parse(
            self.editor.toPlainText(),
            stock_diameter=self.stock_diameter.value(),
            stock_length=self.stock_length.value(),
        )
        self.engine.load(program)
        self._populate_motion_table()
        self._populate_alarm_table()
        errors = sum(a.severity == "error" for a in program.alarms)
        warnings = len(program.alarms) - errors
        self.statusBar().showMessage(f"Parsed {len(program.blocks)} blocks, {len(program.motions)} motions, {errors} errors, {warnings} warnings")
        self.editor.document().setModified(False)
        if errors:
            self.tabs.setCurrentWidget(self.alarm_table)

    def _populate_motion_table(self) -> None:
        motions = self.engine.program.motions if self.engine.program else []
        self.motion_table.setRowCount(len(motions))
        for row, motion in enumerate(motions):
            values = [str(motion.line_index + 1), motion.kind.value, f"{motion.end_x:.3f}", f"{motion.end_z:.3f}", motion.cycle or ""]
            for column, value in enumerate(values):
                self.motion_table.setItem(row, column, QTableWidgetItem(value))
        self.motion_table.resizeColumnsToContents()

    def _populate_alarm_table(self) -> None:
        alarms = self.engine.program.alarms if self.engine.program else []
        self.alarm_table.setRowCount(len(alarms))
        for row, alarm in enumerate(alarms):
            values = [str(alarm.line_index + 1), alarm.code, alarm.message]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if alarm.severity == "error":
                    item.setForeground(QColor("#ff7777"))
                else:
                    item.setForeground(QColor("#ffc866"))
                item.setData(Qt.ItemDataRole.UserRole, alarm.line_index)
                self.alarm_table.setItem(row, column, item)
        self.alarm_table.resizeColumnsToContents()

    def _highlight_line(self, line_index: int) -> None:
        block = self.editor.document().findBlockByLineNumber(line_index)
        cursor = QTextCursor(block)
        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        selection.format = QTextCharFormat()
        selection.format.setBackground(QColor("#214a61"))
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        self.editor.setExtraSelections([selection])
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        motion = self.engine.current_motion
        if motion:
            for row in range(self.motion_table.rowCount()):
                item = self.motion_table.item(row, 0)
                if item and item.text() == str(line_index + 1):
                    self.motion_table.selectRow(row)
                    self.motion_table.scrollToItem(item)
                    break

    def _update_readout(self) -> None:
        motion = self.engine.current_motion
        feed = motion.feed if motion else 0.0
        spindle = motion.spindle if motion else 0.0
        self.readout.setText(f"X {self.engine.tool_x:8.3f}  Z {self.engine.tool_z:8.3f}  F {feed:6.3f}  S {spindle:5.0f}")

    def _go_to_alarm(self, row: int, _column: int) -> None:
        item = self.alarm_table.item(row, 0)
        if not item:
            return
        line = int(item.data(Qt.ItemDataRole.UserRole))
        cursor = QTextCursor(self.editor.document().findBlockByLineNumber(line))
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.editor.document().isModified():
            answer = QMessageBox.question(self, "Unsaved changes", "Close and discard the edited program?")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()
