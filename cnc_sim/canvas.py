"""Custom Qt renderer for the machine and dimensioned drawing views."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget

from .simulation import SimulationEngine


class LatheCanvas(QWidget):
    def __init__(self, engine: SimulationEngine) -> None:
        super().__init__()
        self.engine = engine
        self.mode = "machine"
        self.setMinimumSize(500, 360)
        self.engine.changed.connect(self.update)

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#10161f"))
        self._draw_grid(painter)
        if not self.engine.program:
            painter.setPen(QColor("#91a3b8"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Parse a program to begin")
            return
        if self.mode == "drawing":
            self._draw_drawing(painter)
        else:
            self._draw_machine(painter)

    def _transform(self, z: float, x_radius: float) -> QPointF:
        program = self.engine.program
        assert program
        margin = 55.0
        width = max(1.0, self.width() - margin * 2)
        height = max(1.0, self.height() - margin * 2)
        z_min, z_max = -program.stock_length - 8.0, 12.0
        r_max = program.stock_diameter / 2.0 + 14.0
        px = margin + (z - z_min) / (z_max - z_min) * width
        py = self.height() / 2.0 - x_radius / r_max * (height / 2.0)
        return QPointF(px, py)

    def _draw_grid(self, painter: QPainter) -> None:
        painter.setPen(QPen(QColor(42, 55, 70), 1))
        for x in range(0, self.width(), 40):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 40):
            painter.drawLine(0, y, self.width(), y)

    def _stock_path(self) -> QPainterPath:
        path = QPainterPath()
        points_top: list[QPointF] = []
        points_bottom: list[QPointF] = []
        for i, diameter in enumerate(self.engine.stock_profile):
            z = -i * self.engine.profile_step
            points_top.append(self._transform(z, diameter / 2.0))
            points_bottom.append(self._transform(z, -diameter / 2.0))
        if not points_top:
            return path
        path.moveTo(points_top[0])
        for point in points_top[1:]:
            path.lineTo(point)
        for point in reversed(points_bottom):
            path.lineTo(point)
        path.closeSubpath()
        return path

    def _draw_machine(self, painter: QPainter) -> None:
        program = self.engine.program
        assert program
        center_y = self._transform(0, 0).y()
        painter.setPen(QPen(QColor("#688198"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(25, int(center_y), self.width() - 25, int(center_y))

        stock = self._stock_path()
        painter.fillPath(stock, QColor("#c68b32"))
        painter.setPen(QPen(QColor("#f0bd5b"), 2))
        painter.drawPath(stock)

        # Chuck jaws at positive Z.
        chuck_x = self._transform(5, 0).x()
        painter.fillRect(QRectF(chuck_x, center_y - 75, 35, 150), QColor("#596676"))
        painter.fillRect(QRectF(chuck_x - 20, center_y - 68, 25, 25), QColor("#8191a3"))
        painter.fillRect(QRectF(chuck_x - 20, center_y + 43, 25, 25), QColor("#8191a3"))

        # Programmed toolpath.
        if program.motions:
            painter.setPen(QPen(QColor(76, 188, 255, 125), 1.5, Qt.PenStyle.DashLine))
            for motion in program.motions:
                a = self._transform(motion.start_z, motion.start_x / 2.0)
                b = self._transform(motion.end_z, motion.end_x / 2.0)
                painter.drawLine(a, b)

        # Tool is shown above the stock; X is diameter programmed.
        tip = self._transform(self.engine.tool_z, self.engine.tool_x / 2.0)
        tool = QPolygonF([tip, tip + QPointF(22, -10), tip + QPointF(32, -32), tip + QPointF(8, -24)])
        painter.setPen(QPen(QColor("#e6f2ff"), 2))
        painter.setBrush(QColor("#e85151"))
        painter.drawPolygon(tool)
        painter.setPen(QColor("#dbe8f5"))
        painter.setFont(QFont("Consolas", 9))
        painter.drawText(16, 24, f"X {self.engine.tool_x:8.3f}   Z {self.engine.tool_z:8.3f}")

    def _draw_drawing(self, painter: QPainter) -> None:
        program = self.engine.program
        assert program
        stock = self._stock_path()
        painter.setBrush(QColor(33, 66, 86))
        painter.setPen(QPen(QColor("#76d0ff"), 2))
        painter.drawPath(stock)
        center = self._transform(0, 0).y()
        painter.setPen(QPen(QColor("#8fa7ba"), 1, Qt.PenStyle.DashDotLine))
        painter.drawLine(25, int(center), self.width() - 25, int(center))

        painter.setFont(QFont("Arial", 9))
        painter.setPen(QColor("#dce9f4"))
        left = self._transform(-program.stock_length, 0).x()
        right = self._transform(0, 0).x()
        dim_y = self.height() - 34
        painter.drawLine(QPointF(left, dim_y), QPointF(right, dim_y))
        painter.drawLine(QPointF(left, dim_y - 7), QPointF(left, dim_y + 7))
        painter.drawLine(QPointF(right, dim_y - 7), QPointF(right, dim_y + 7))
        painter.drawText(QRectF(left, dim_y - 25, right - left, 20), Qt.AlignmentFlag.AlignCenter, f"{program.stock_length:.1f} mm")

        z_at_max = 0.0
        max_diameter = max(self.engine.stock_profile, default=program.stock_diameter)
        px = self._transform(z_at_max, max_diameter / 2).x() + 30
        top = self._transform(z_at_max, max_diameter / 2).y()
        bottom = self._transform(z_at_max, -max_diameter / 2).y()
        painter.drawLine(QPointF(px, top), QPointF(px, bottom))
        painter.drawLine(QPointF(px - 7, top), QPointF(px + 7, top))
        painter.drawLine(QPointF(px - 7, bottom), QPointF(px + 7, bottom))
        painter.drawText(QPointF(px + 8, center + 5), f"Ø{max_diameter:.1f}")
        painter.drawText(18, 24, "TRAINING DRAWING — GENERATED FROM SIMULATED PROFILE")
