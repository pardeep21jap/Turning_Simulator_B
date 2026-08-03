"""Custom Qt renderer for the machine and dimensioned drawing views."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget

from .dimensioning import ChamferDim, DiameterDim, LengthDim, RadiusDim, extract_dimensions
from .simulation import SimulationEngine

THEMES: dict[str, dict[str, QColor]] = {
    "dark": {
        "background": QColor("#10161f"),
        "grid": QColor(42, 55, 70),
        "empty_text": QColor("#91a3b8"),
        "centerline": QColor("#688198"),
        "raw_light": QColor("#5bb7e0"),
        "raw_dark": QColor("#1c4f66"),
        "cut_light": QColor("#f0bd5b"),
        "cut_dark": QColor("#8a5a1c"),
        "chuck_light": QColor("#9aa9b8"),
        "chuck_dark": QColor("#40505f"),
        "jaw_light": QColor("#b7c3cf"),
        "jaw_dark": QColor("#586878"),
        "chuck_outline": QColor("#c7d3de"),
        "jaw_outline": QColor("#d6dfe7"),
        "toolpath": QColor(76, 188, 255, 125),
        "tool_outline": QColor("#e6f2ff"),
        "tool_light": QColor("#f27b7b"),
        "tool_dark": QColor("#8f2020"),
        "readout_text": QColor("#dbe8f5"),
        "part_light": QColor("#c3d3de"),
        "part_dark": QColor("#5c707f"),
        "part_outline": QColor("#e7f1f8"),
        "drawing_centerline": QColor("#8fa7ba"),
        "title_text": QColor("#dce9f4"),
        "dim_ext": QColor("#9fb3c2"),
        "dim_line": QColor("#dce9f4"),
        "radius_leader": QColor("#ffce7a"),
        "chamfer_leader": QColor("#8fe0ff"),
    },
    "light": {
        "background": QColor("#eef2f6"),
        "grid": QColor(206, 216, 226),
        "empty_text": QColor("#5b6b7a"),
        "centerline": QColor("#7c8fa0"),
        "raw_light": QColor("#7fc7ea"),
        "raw_dark": QColor("#2a6e8c"),
        "cut_light": QColor("#f2c877"),
        "cut_dark": QColor("#a06e1f"),
        "chuck_light": QColor("#c3ccd4"),
        "chuck_dark": QColor("#7c8b99"),
        "jaw_light": QColor("#d3dae0"),
        "jaw_dark": QColor("#93a1ae"),
        "chuck_outline": QColor("#4f5d6b"),
        "jaw_outline": QColor("#4f5d6b"),
        "toolpath": QColor(30, 110, 170, 140),
        "tool_outline": QColor("#5b1414"),
        "tool_light": QColor("#f28a8a"),
        "tool_dark": QColor("#941f1f"),
        "readout_text": QColor("#1f2933"),
        "part_light": QColor("#f4f7fa"),
        "part_dark": QColor("#9fb0bd"),
        "part_outline": QColor("#3d4b58"),
        "drawing_centerline": QColor("#5b6b7a"),
        "title_text": QColor("#1f2933"),
        "dim_ext": QColor("#5b6b7a"),
        "dim_line": QColor("#1f2933"),
        "radius_leader": QColor("#a35d0a"),
        "chamfer_leader": QColor("#0e7490"),
    },
}


class LatheCanvas(QWidget):
    def __init__(self, engine: SimulationEngine) -> None:
        super().__init__()
        self.engine = engine
        self.mode = "machine"
        self.theme = "dark"
        self.setMinimumSize(500, 360)
        self.engine.changed.connect(self.update)

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.update()

    def set_theme(self, theme: str) -> None:
        self.theme = theme
        self.update()

    def _colors(self) -> dict[str, QColor]:
        return THEMES[self.theme]

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colors = self._colors()
        painter.fillRect(self.rect(), colors["background"])
        self._draw_grid(painter, colors)
        if not self.engine.program:
            painter.setPen(colors["empty_text"])
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Parse a program to begin")
            return
        if self.mode == "drawing":
            self._draw_drawing(painter, colors)
        else:
            self._draw_machine(painter, colors)

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

    def _draw_grid(self, painter: QPainter, colors: dict[str, QColor]) -> None:
        painter.setPen(QPen(colors["grid"], 1))
        for x in range(0, self.width(), 40):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 40):
            painter.drawLine(0, y, self.width(), y)

    def _cylinder_gradient(self, rect: QRectF, light: QColor, dark: QColor) -> QLinearGradient:
        top, bottom = rect.top(), rect.bottom()
        if bottom - top < 1.0:
            bottom = top + 1.0
        gradient = QLinearGradient(0.0, top, 0.0, bottom)
        gradient.setColorAt(0.0, dark)
        gradient.setColorAt(0.16, light)
        gradient.setColorAt(0.5, light.lighter(120))
        gradient.setColorAt(0.84, light)
        gradient.setColorAt(1.0, dark)
        return gradient

    def _stock_path(self, profile: list[float] | None = None) -> QPainterPath:
        return self._segment_path(self.engine.stock_profile if profile is None else profile, 0, None)

    def _segment_path(self, profile: list[float], start: int, end: int | None) -> QPainterPath:
        path = QPainterPath()
        last = len(profile) - 1 if end is None else end
        points_top: list[QPointF] = []
        points_bottom: list[QPointF] = []
        for i in range(start, last + 1):
            z = -i * self.engine.profile_step
            diameter = profile[i]
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

    def _profile_runs(self, profile: list[float], stock_diameter: float) -> list[tuple[int, int, bool]]:
        if not profile:
            return []
        runs: list[tuple[int, int, bool]] = []
        start = 0
        current_cut = profile[0] < stock_diameter - 0.05
        for i in range(1, len(profile)):
            is_cut = profile[i] < stock_diameter - 0.05
            if is_cut != current_cut:
                runs.append((start, i, current_cut))
                start = i
                current_cut = is_cut
        runs.append((start, len(profile) - 1, current_cut))
        return runs

    def _draw_machine(self, painter: QPainter, colors: dict[str, QColor]) -> None:
        program = self.engine.program
        assert program
        center_y = self._transform(0, 0).y()
        painter.setPen(QPen(colors["centerline"], 1, Qt.PenStyle.DashLine))
        painter.drawLine(25, int(center_y), self.width() - 25, int(center_y))

        for start, end, is_cut in self._profile_runs(self.engine.stock_profile, program.stock_diameter):
            segment = self._segment_path(self.engine.stock_profile, start, end)
            if segment.isEmpty():
                continue
            light, dark = (
                (colors["cut_light"], colors["cut_dark"]) if is_cut else (colors["raw_light"], colors["raw_dark"])
            )
            painter.fillPath(segment, self._cylinder_gradient(segment.boundingRect(), light, dark))
            painter.setPen(QPen(light.lighter(130), 1.4))
            painter.drawPath(segment)

        # Chuck jaws at positive Z.
        chuck_x = self._transform(5, 0).x()
        chuck_rect = QRectF(chuck_x, center_y - 75, 35, 150)
        painter.fillRect(chuck_rect, self._cylinder_gradient(chuck_rect, colors["chuck_light"], colors["chuck_dark"]))
        painter.setPen(QPen(colors["chuck_outline"], 1))
        painter.drawRect(chuck_rect)
        for jaw_y in (center_y - 68, center_y + 43):
            jaw_rect = QRectF(chuck_x - 20, jaw_y, 25, 25)
            painter.fillRect(jaw_rect, self._cylinder_gradient(jaw_rect, colors["jaw_light"], colors["jaw_dark"]))
            painter.setPen(QPen(colors["jaw_outline"], 1))
            painter.drawRect(jaw_rect)

        # Programmed toolpath.
        if program.motions:
            painter.setPen(QPen(colors["toolpath"], 1.5, Qt.PenStyle.DashLine))
            for motion in program.motions:
                a = self._transform(motion.start_z, motion.start_x / 2.0)
                b = self._transform(motion.end_z, motion.end_x / 2.0)
                painter.drawLine(a, b)

        # Tool is shown above the stock; X is diameter programmed.
        tip = self._transform(self.engine.tool_z, self.engine.tool_x / 2.0)
        tool = QPolygonF([tip, tip + QPointF(22, -10), tip + QPointF(32, -32), tip + QPointF(8, -24)])
        tool_rect = QRectF(tip.x(), tip.y() - 32, 32, 32)
        painter.setPen(QPen(colors["tool_outline"], 2))
        painter.setBrush(self._cylinder_gradient(tool_rect, colors["tool_light"], colors["tool_dark"]))
        painter.drawPolygon(tool)
        painter.setPen(colors["readout_text"])
        painter.setFont(QFont("Consolas", 9))
        painter.drawText(16, 24, f"X {self.engine.tool_x:8.3f}   Z {self.engine.tool_z:8.3f}")

    def _draw_drawing(self, painter: QPainter, colors: dict[str, QColor]) -> None:
        program = self.engine.program
        assert program
        stock = self._stock_path(self.engine.final_profile)
        part_rect = stock.boundingRect()
        painter.setBrush(self._cylinder_gradient(part_rect, colors["part_light"], colors["part_dark"]))
        painter.setPen(QPen(colors["part_outline"], 1.6))
        painter.drawPath(stock)

        center = self._transform(0, 0).y()
        painter.setPen(QPen(colors["drawing_centerline"], 1, Qt.PenStyle.DashDotLine))
        painter.drawLine(25, int(center), self.width() - 25, int(center))

        painter.setFont(QFont("Arial", 9))
        painter.setPen(colors["title_text"])
        painter.drawText(18, 24, "TRAINING DRAWING — GENERATED FROM SIMULATED PROFILE")

        dims = extract_dimensions(program)
        self._draw_diameter_dims(painter, colors, dims.diameters, part_rect)
        self._draw_length_dims(painter, colors, dims.lengths, part_rect)
        self._draw_radius_dims(painter, colors, dims.radii)
        self._draw_chamfer_dims(painter, colors, dims.chamfers)

    def _draw_diameter_dims(
        self, painter: QPainter, colors: dict[str, QColor], diameters: list[DiameterDim], part_rect: QRectF
    ) -> None:
        if not diameters:
            return
        painter.setFont(QFont("Arial", 8))
        gap = 26.0
        ordered = sorted(diameters, key=lambda d: min(d.z_start, d.z_end))
        for i, dim in enumerate(ordered):
            top = self._transform(dim.z_end, dim.diameter / 2.0)
            bottom = self._transform(dim.z_end, -dim.diameter / 2.0)
            line_x = part_rect.right() + gap * (i + 1)
            painter.setPen(QPen(colors["dim_ext"], 1))
            painter.drawLine(top, QPointF(line_x, top.y()))
            painter.drawLine(bottom, QPointF(line_x, bottom.y()))
            painter.setPen(QPen(colors["dim_line"], 1.2))
            painter.drawLine(QPointF(line_x, top.y()), QPointF(line_x, bottom.y()))
            painter.drawLine(QPointF(line_x - 4, top.y()), QPointF(line_x + 4, top.y()))
            painter.drawLine(QPointF(line_x - 4, bottom.y()), QPointF(line_x + 4, bottom.y()))
            painter.save()
            painter.translate(line_x + 12, (top.y() + bottom.y()) / 2.0)
            painter.rotate(-90)
            painter.drawText(QRectF(-40, -8, 80, 16), Qt.AlignmentFlag.AlignCenter, f"Ø{dim.diameter:.1f}")
            painter.restore()

    def _draw_length_dims(
        self, painter: QPainter, colors: dict[str, QColor], lengths: list[LengthDim], part_rect: QRectF
    ) -> None:
        if not lengths:
            return
        painter.setFont(QFont("Arial", 8))
        ordered = sorted(lengths, key=lambda d: min(d.z_start, d.z_end))
        rows: list[float] = []
        placements: list[tuple[LengthDim, int, float, float]] = []
        for dim in ordered:
            a = self._transform(dim.z_start, 0).x()
            b = self._transform(dim.z_end, 0).x()
            left, right = min(a, b), max(a, b)
            row_index = None
            for r, last_right in enumerate(rows):
                if left > last_right + 8:
                    rows[r] = right
                    row_index = r
                    break
            if row_index is None:
                rows.append(right)
                row_index = len(rows) - 1
            placements.append((dim, row_index, left, right))

        part_bottom = part_rect.bottom() + 6
        base_y = self.height() - 20
        row_height = 24
        for dim, row_index, left, right in placements:
            y = base_y - row_index * row_height
            painter.setPen(QPen(colors["dim_ext"], 1))
            painter.drawLine(QPointF(left, part_bottom), QPointF(left, y))
            painter.drawLine(QPointF(right, part_bottom), QPointF(right, y))
            painter.setPen(QPen(colors["dim_line"], 1.2))
            painter.drawLine(QPointF(left, y), QPointF(right, y))
            painter.drawLine(QPointF(left, y - 4), QPointF(left, y + 4))
            painter.drawLine(QPointF(right, y - 4), QPointF(right, y + 4))
            painter.drawText(QRectF(left, y - 18, right - left, 16), Qt.AlignmentFlag.AlignCenter, f"{dim.length:.1f}")

    def _draw_radius_dims(self, painter: QPainter, colors: dict[str, QColor], radii: list[RadiusDim]) -> None:
        painter.setFont(QFont("Arial", 8))
        for i, dim in enumerate(radii):
            point = self._transform(dim.z, dim.x_radius)
            length = 30 + (i % 3) * 16
            end = QPointF(point.x() - length * 0.7, point.y() - length * 0.7)
            painter.setPen(QPen(colors["radius_leader"], 1.3))
            painter.drawLine(point, end)
            painter.drawEllipse(point, 2.2, 2.2)
            painter.setPen(colors["radius_leader"])
            label_rect = QRectF(end.x() - 42, end.y() - 18, 40, 16)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"R{dim.radius:.1f}")

    def _draw_chamfer_dims(self, painter: QPainter, colors: dict[str, QColor], chamfers: list[ChamferDim]) -> None:
        painter.setFont(QFont("Arial", 8))
        for i, dim in enumerate(chamfers):
            point = self._transform(dim.z, dim.x_radius)
            length = 30 + (i % 3) * 16
            end = QPointF(point.x() - length * 0.7, point.y() - length * 0.7)
            painter.setPen(QPen(colors["chamfer_leader"], 1.3))
            painter.drawLine(point, end)
            painter.drawEllipse(point, 2.2, 2.2)
            painter.setPen(colors["chamfer_leader"])
            label_rect = QRectF(end.x() - 76, end.y() - 18, 74, 16)
            painter.drawText(
                label_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{dim.leg:.1f} x {dim.angle:.0f}°"
            )
