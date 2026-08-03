"""Main PyQt6 desktop interface."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRegularExpression, Qt
from PyQt6.QtGui import (
    QAction,
    QColor,
    QKeySequence,
    QPainter,
    QPixmap,
    QRegularExpressionValidator,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
)
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFormLayout,
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

from .canvas import DEFAULT_TOOL_ASSIGNMENTS, LatheCanvas
from .examples import EXAMPLES
from .lathe_core import spindle_rpm
from .models import Program
from .parser import FanucParser
from .simulation import SimulationEngine
from .styles import DARK_STYLESHEET, LIGHT_STYLESHEET

GCODE_LABELS = {0: "G00", 1: "G01", 2: "G02", 3: "G03"}


def _mode_label(g: int) -> str:
    return GCODE_LABELS.get(g, f"G{g:02d}")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CNC Lathe Simulator — FANUC Training")
        self.resize(1440, 850)
        self.theme = "dark"
        self.tool_assignments = dict(DEFAULT_TOOL_ASSIGNMENTS)
        self._cycle_selections: list[QTextEdit.ExtraSelection] = []
        self._current_line_selection: QTextEdit.ExtraSelection | None = None
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
        self.stock_diameter.setToolTip("Auto-detected from the program on each parse")
        controls.addWidget(self.stock_diameter)
        controls.addWidget(QLabel("Length"))
        self.stock_length = QDoubleSpinBox()
        self.stock_length.setRange(10.0, 500.0)
        self.stock_length.setValue(100.0)
        self.stock_length.setSuffix(" mm")
        self.stock_length.setToolTip("Auto-detected from the program on each parse")
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
        tool_setup_button = QPushButton("Tool Setup")
        tool_setup_button.setToolTip("Assign tool stations to machining operations")
        tool_setup_button.clicked.connect(self._show_tool_setup)
        controls.addWidget(tool_setup_button)
        controls.addWidget(QLabel("Speed"))
        speed = QDoubleSpinBox()
        speed.setRange(0.1, 10.0)
        speed.setSingleStep(0.25)
        speed.setValue(1.0)
        speed.setSuffix("×")
        speed.valueChanged.connect(self.engine.set_speed)
        controls.addWidget(speed)
        controls.addStretch(1)
        self.theme_button = QPushButton("☀ Light Mode")
        self.theme_button.clicked.connect(self._toggle_theme)
        controls.addWidget(self.theme_button)
        root_layout.addLayout(controls)
        root_layout.addWidget(self._build_dro_row())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.editor = QPlainTextEdit()
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.editor.setMinimumWidth(340)
        splitter.addWidget(self.editor)

        center = QSplitter(Qt.Orientation.Vertical)

        machine_pane = QWidget()
        machine_layout = QVBoxLayout(machine_pane)
        machine_layout.setContentsMargins(0, 0, 0, 4)
        machine_layout.addWidget(QLabel("Machine View"))
        self.machine_canvas = LatheCanvas(self.engine)
        self.machine_canvas.set_mode("machine")
        machine_layout.addWidget(self.machine_canvas, 1)
        center.addWidget(machine_pane)

        drawing_pane = QWidget()
        drawing_layout = QVBoxLayout(drawing_pane)
        drawing_layout.setContentsMargins(0, 4, 0, 0)
        drawing_layout.addWidget(QLabel("Drawing View"))
        self.drawing_canvas = LatheCanvas(self.engine)
        self.drawing_canvas.set_mode("drawing")
        drawing_layout.addWidget(self.drawing_canvas, 1)
        center.addWidget(drawing_pane)

        center.setSizes([1, 1])
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

    def _show_tool_setup(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Tool Setup")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Select a preset or type a custom tool number from T01 to T99."))
        form = QFormLayout()
        choices: dict[str, QComboBox] = {}
        previews: dict[str, QLabel] = {}
        labels = (
            ("turning", "Turning / Facing"),
            ("roughing", "Roughing / Face Cycle"),
            ("boring", "Boring"),
            ("drilling", "Drilling"),
        )
        stations = [f"T{station:02d}" for station in range(1, 13)]
        tool_validator = QRegularExpressionValidator(QRegularExpression(r"T(?:0[1-9]|[1-9][0-9])"))
        for operation, label in labels:
            combo = QComboBox()
            combo.addItems(stations)
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            combo.lineEdit().setValidator(tool_validator)
            combo.lineEdit().setPlaceholderText("T01–T99")
            combo.setCurrentText(f"T{self.tool_assignments[operation]:02d}")
            preview = QLabel()
            preview.setFixedSize(155, 100)
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            selector_row = QWidget()
            selector_layout = QHBoxLayout(selector_row)
            selector_layout.setContentsMargins(0, 0, 0, 0)
            selector_layout.addWidget(combo)
            selector_layout.addWidget(preview)
            form.addRow(label, selector_row)
            choices[operation] = combo
            previews[operation] = preview
            combo.currentTextChanged.connect(
                lambda tool, op=operation: self._update_tool_preview(previews[op], op, tool)
            )
            self._update_tool_preview(preview, operation, combo.currentText())
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if any(not combo.lineEdit().hasAcceptableInput() for combo in choices.values()):
            QMessageBox.warning(self, "Tool Setup", "Enter each custom tool number in T01–T99 format.")
            return
        selected = {
            operation: int(combo.currentText()[1:])
            for operation, combo in choices.items()
        }
        if len(set(selected.values())) != len(selected):
            QMessageBox.warning(self, "Tool Setup", "Each operation must use a different tool station.")
            return
        self.tool_assignments = selected
        self.machine_canvas.set_tool_assignments(selected)
        self.drawing_canvas.set_tool_assignments(selected)
        summary = ", ".join(f"{label}: T{selected[key]:02d}" for key, label in labels)
        self.statusBar().showMessage(f"Tool setup updated — {summary}", 8000)

    def _update_tool_preview(self, label: QLabel, operation: str, tool: str) -> None:
        pixmap = QPixmap(label.size())
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        style = {"boring": "boring", "drilling": "drill"}.get(operation, "turning")
        tip = QPointF(12, 94) if style == "turning" else QPointF(12, 52)
        self.machine_canvas._draw_tool_icon(painter, self.machine_canvas._colors(), tip, style)
        painter.end()
        label.setPixmap(pixmap)
        label.setToolTip(f"{tool or 'Custom tool'} — {operation.replace('_', ' ').title()}")

    def _build_dro_row(self) -> QWidget:
        row = QFrame()
        row.setObjectName("droRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(22)
        self.dro: dict[str, QLabel] = {}
        for key, caption in (
            ("X", "X Ø"),
            ("Z", "Z"),
            ("F", "FEED mm/rev"),
            ("S", "SPINDLE"),
            ("G", "MODE"),
            ("T", "TOOL"),
            ("R", "REMOVED"),
        ):
            cell = QVBoxLayout()
            cell.setSpacing(0)
            caption_label = QLabel(caption)
            caption_label.setObjectName("droCaption")
            value_label = QLabel("--")
            value_label.setObjectName("droValue")
            cell.addWidget(caption_label)
            cell.addWidget(value_label)
            layout.addLayout(cell)
            self.dro[key] = value_label
        layout.addStretch(1)
        return row

    def _toggle_theme(self) -> None:
        self.theme = "light" if self.theme == "dark" else "dark"
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(LIGHT_STYLESHEET if self.theme == "light" else DARK_STYLESHEET)
        self.machine_canvas.set_theme(self.theme)
        self.drawing_canvas.set_theme(self.theme)
        self.theme_button.setText("🌙 Dark Mode" if self.theme == "light" else "☀ Light Mode")
        if self.engine.program:
            self._cycle_selections = self._build_cycle_selections(self.engine.program)
        if self.engine.current_seg:
            self._highlight_line(self.engine.current_seg.line)
        else:
            self._apply_selections()

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
        text = self.editor.toPlainText()
        draft = self.parser.parse(
            text,
            stock_diameter=self.stock_diameter.value(),
            stock_length=self.stock_length.value(),
        )
        diameter, length = self._detect_stock(draft)
        self.stock_diameter.setValue(diameter)
        self.stock_length.setValue(length)
        program = self.parser.parse(text, stock_diameter=diameter, stock_length=length)
        self.engine.load(program)
        self._cycle_selections = self._build_cycle_selections(program)
        self._apply_selections()
        self._populate_motion_table()
        self._populate_alarm_table()
        errors = sum(m.kind == "err" for m in program.msgs)
        notes = len(program.msgs) - errors
        self.statusBar().showMessage(
            f"Compiled {len(program.lines)} lines, {len(program.segs)} segments, {errors} errors, {notes} notes"
        )
        self.editor.document().setModified(False)
        if errors:
            self.tabs.setCurrentWidget(self.alarm_table)

    def _detect_stock(self, program: Program) -> tuple[float, float]:
        """Estimate a snug stock size from the widest/deepest cutting segment."""
        cuts = [s for s in program.segs if not s.rapid]
        if not cuts:
            return self.stock_diameter.value(), self.stock_length.value()
        # Facing cuts often begin at the stock OD and end at a much smaller
        # radius, so both ends of every cutting segment must be considered.
        max_diameter = max(max(s.r0, s.r1) * 2.0 for s in cuts)
        min_z = min(s.z1 for s in cuts)
        diameter = min(300.0, max(5.0, max_diameter + 2.0))
        length = min(500.0, max(10.0, abs(min_z) + 5.0))
        return diameter, length

    def _populate_motion_table(self) -> None:
        program = self.engine.program
        segs = program.segs if program else []
        self.motion_table.setRowCount(len(segs))
        for row, seg in enumerate(segs):
            cycle = "cycle" if program and seg.line in program.cycle_lines else ""
            values = [str(seg.line + 1), _mode_label(seg.g), f"{seg.r1 * 2.0:.3f}", f"{seg.z1:.3f}", cycle]
            for column, value in enumerate(values):
                self.motion_table.setItem(row, column, QTableWidgetItem(value))
        self.motion_table.resizeColumnsToContents()

    def _populate_alarm_table(self) -> None:
        msgs = self.engine.program.msgs if self.engine.program else []
        self.alarm_table.setRowCount(len(msgs))
        for row, msg in enumerate(msgs):
            values = [str(msg.line + 1), msg.kind.upper(), msg.text]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setForeground(QColor("#ff7777") if msg.kind == "err" else QColor("#8ee6b8"))
                item.setData(Qt.ItemDataRole.UserRole, msg.line)
                self.alarm_table.setItem(row, column, item)
        self.alarm_table.resizeColumnsToContents()

    def _build_cycle_selections(self, program: Program) -> list[QTextEdit.ExtraSelection]:
        color = QColor("#0e7490") if self.theme == "light" else QColor("#49c9dd")
        selections = []
        for line in sorted(program.cycle_lines):
            selection = QTextEdit.ExtraSelection()
            selection.cursor = QTextCursor(self.editor.document().findBlockByLineNumber(line))
            selection.format = QTextCharFormat()
            selection.format.setForeground(color)
            selections.append(selection)
        return selections

    def _apply_selections(self) -> None:
        selections = list(self._cycle_selections)
        if self._current_line_selection is not None:
            selections.append(self._current_line_selection)
        self.editor.setExtraSelections(selections)

    def _highlight_line(self, line_index: int) -> None:
        block = self.editor.document().findBlockByLineNumber(line_index)
        cursor = QTextCursor(block)
        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        selection.format = QTextCharFormat()
        selection.format.setBackground(QColor("#bfe0f5") if self.theme == "light" else QColor("#214a61"))
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        self._current_line_selection = selection
        self._apply_selections()
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        seg = self.engine.current_seg
        if seg:
            for row in range(self.motion_table.rowCount()):
                item = self.motion_table.item(row, 0)
                if item and item.text() == str(line_index + 1):
                    self.motion_table.selectRow(row)
                    self.motion_table.scrollToItem(item)
                    break

    def _update_readout(self) -> None:
        seg = self.engine.current_seg
        program = self.engine.program
        feed = seg.feed if seg else 0.0
        mode = _mode_label(seg.g) if seg else "--"
        if seg:
            tool = seg.tool
            rpm = spindle_rpm(self.engine.tool_x, seg.css, seg.clamp, seg.sval)
        elif program and program.segs:
            tool = program.segs[-1].tool
            rpm = 0.0
        else:
            tool = "T00"
            rpm = 0.0
        self.dro["X"].setText(f"{self.engine.tool_x:.3f}")
        self.dro["Z"].setText(f"{self.engine.tool_z:.3f}")
        self.dro["F"].setText(f"{feed:.3f}")
        self.dro["S"].setText(f"{rpm:.0f}")
        self.dro["G"].setText(mode)
        self.dro["T"].setText(tool)
        self.dro["R"].setText(f"{self.engine.removed_fraction() * 100:.0f}%")

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
