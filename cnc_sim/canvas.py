"""Custom Qt renderer for the machine and dimensioned drawing views."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget

from .dimensioning import ChamferDim, DiameterDim, LengthDim, RadiusDim, extract_dimensions
from .lathe_core import Stock
from .simulation import SimulationEngine

DEFAULT_TOOL_STYLE = "turning"
DEFAULT_TOOL_ASSIGNMENTS: dict[str, int] = {
    "turning": 1,
    "roughing": 2,
    "boring": 3,
    "drilling": 4,
}


def tool_styles(assignments: dict[str, int]) -> dict[int, str]:
    """Convert operation-to-station choices into renderer styles."""
    styles = {
        assignments["turning"]: "turning",
        assignments["roughing"]: "turning",
        assignments["boring"]: "boring",
        assignments["drilling"]: "drill",
    }
    if 5 not in assignments.values():
        styles[5] = "grooving"
    return styles


def _tool_station(tool: str) -> int:
    digits = "".join(ch for ch in tool if ch.isdigit())
    return int(digits) if digits else 0

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
        "toolpath": QColor(76, 188, 255, 125),
        "tool_outline": QColor("#e6f2ff"),
        "tool_light": QColor("#f27b7b"),
        "tool_dark": QColor("#8f2020"),
        "tool_body_light": QColor("#aab8c4"),
        "tool_body_dark": QColor("#4c5966"),
        "insert_light": QColor("#f2e07a"),
        "insert_dark": QColor("#a68f2c"),
        "general_tool_outline": QColor("#77818a"),
        "boring_bar_light": QColor("#3a3d40"),
        "boring_bar_dark": QColor("#050505"),
        "boring_pocket_light": QColor("#d9b23c"),
        "boring_pocket_dark": QColor("#7a5a12"),
        "boring_screw": QColor("#9aa2a8"),
        "drill_shank_light": QColor("#e4e8eb"),
        "drill_shank_dark": QColor("#737b81"),
        "drill_flute_light": QColor("#555d62"),
        "drill_flute_dark": QColor("#101315"),
        "drill_land": QColor("#c5cbd0"),
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
        "origin": QColor("#ff5c5c"),
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
        "toolpath": QColor(30, 110, 170, 140),
        "tool_outline": QColor("#5b1414"),
        "tool_light": QColor("#f28a8a"),
        "tool_dark": QColor("#941f1f"),
        "tool_body_light": QColor("#c7d0d8"),
        "tool_body_dark": QColor("#8a97a3"),
        "insert_light": QColor("#f0d968"),
        "insert_dark": QColor("#8f7a1f"),
        "general_tool_outline": QColor("#777777"),
        "boring_bar_light": QColor("#3a3d40"),
        "boring_bar_dark": QColor("#050505"),
        "boring_pocket_light": QColor("#d9b23c"),
        "boring_pocket_dark": QColor("#7a5a12"),
        "boring_screw": QColor("#8a97a3"),
        "drill_shank_light": QColor("#e4e8eb"),
        "drill_shank_dark": QColor("#737b81"),
        "drill_flute_light": QColor("#555d62"),
        "drill_flute_dark": QColor("#101315"),
        "drill_land": QColor("#c5cbd0"),
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
        "origin": QColor("#c0392b"),
    },
}


class LatheCanvas(QWidget):
    def __init__(self, engine: SimulationEngine) -> None:
        super().__init__()
        self.engine = engine
        self.mode = "machine"
        self.theme = "dark"
        self.tool_assignments = dict(DEFAULT_TOOL_ASSIGNMENTS)
        self.setMinimumSize(500, 360)
        self.engine.changed.connect(self.update)

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.update()

    def set_theme(self, theme: str) -> None:
        self.theme = theme
        self.update()

    def set_tool_assignments(self, assignments: dict[str, int]) -> None:
        self.tool_assignments = dict(assignments)
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
        # One shared scale for both axes so the part isn't stretched out of proportion.
        scale = min(width / (z_max - z_min), height / (2.0 * r_max))
        center_x = margin + width / 2.0
        center_y = self.height() / 2.0
        px = center_x + (z - (z_min + z_max) / 2.0) * scale
        py = center_y - x_radius * scale
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

    def _stride_for(self, stock: Stock) -> int:
        return max(1, stock.n // 800)

    def _stock_path(self, stock: Stock | None = None) -> QPainterPath:
        st = stock if stock is not None else self.engine.live_stock
        if st is None:
            return QPainterPath()
        return self._segment_path(st, 0, st.n - 1, self._stride_for(st))

    def _segment_path(self, stock: Stock, start: int, end: int, stride: int) -> QPainterPath:
        path = QPainterPath()
        path.setFillRule(Qt.FillRule.OddEvenFill)
        points_top: list[QPointF] = []
        points_bottom: list[QPointF] = []
        bore_top: list[QPointF] = []
        bore_bottom: list[QPointF] = []
        for i in range(start, end + 1, stride):
            z = stock.z_at(i)
            r = stock.rad[i]
            points_top.append(self._transform(z, r))
            points_bottom.append(self._transform(z, -r))
            inner = stock.inner[i]
            bore_top.append(self._transform(z, inner))
            bore_bottom.append(self._transform(z, -inner))
        if not points_top:
            return path
        path.moveTo(points_top[0])
        for point in points_top[1:]:
            path.lineTo(point)
        for point in reversed(points_bottom):
            path.lineTo(point)
        path.closeSubpath()
        if any(stock.inner[i] > 0.0 for i in range(start, end + 1, stride)):
            path.moveTo(bore_top[0])
            for point in bore_top[1:]:
                path.lineTo(point)
            for point in reversed(bore_bottom):
                path.lineTo(point)
            path.closeSubpath()
        return path

    def _profile_runs(self, stock: Stock, stride: int) -> list[tuple[int, int, bool]]:
        indices = [i for i in range(0, stock.n, stride) if stock.rad[i] > 0]
        if not indices:
            return []
        runs: list[tuple[int, int, bool]] = []
        start = prev = indices[0]
        current_cut = bool(stock.cut[start])
        for i in indices[1:]:
            is_cut = bool(stock.cut[i])
            if is_cut != current_cut or i - prev > stride:
                runs.append((start, prev, current_cut))
                start = i
                current_cut = is_cut
            prev = i
        runs.append((start, prev, current_cut))
        return runs

    def _draw_origin(self, painter: QPainter, colors: dict[str, QColor]) -> None:
        point = self._transform(0, 0)
        color = colors["origin"]
        radius = 9.0

        rect = QRectF(point.x() - radius, point.y() - radius, radius * 2, radius * 2)
        painter.setPen(QPen(color, 1.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect)
        painter.setBrush(color)
        painter.drawPie(rect, 0, 90 * 16)
        painter.drawPie(rect, 180 * 16, 90 * 16)
        painter.drawLine(QPointF(point.x() - radius, point.y()), QPointF(point.x() + radius, point.y()))
        painter.drawLine(QPointF(point.x(), point.y() - radius), QPointF(point.x(), point.y() + radius))

    def _draw_machine(self, painter: QPainter, colors: dict[str, QColor]) -> None:
        program = self.engine.program
        assert program
        center_y = self._transform(0, 0).y()
        painter.setPen(QPen(colors["centerline"], 1, Qt.PenStyle.DashLine))
        painter.drawLine(25, int(center_y), self.width() - 25, int(center_y))

        live_stock = self.engine.live_stock
        if live_stock is not None:
            stride = self._stride_for(live_stock)
            for start, end, is_cut in self._profile_runs(live_stock, stride):
                segment = self._segment_path(live_stock, start, end, stride)
                if segment.isEmpty():
                    continue
                light, dark = (
                    (colors["cut_light"], colors["cut_dark"]) if is_cut else (colors["raw_light"], colors["raw_dark"])
                )
                painter.fillPath(segment, self._cylinder_gradient(segment.boundingRect(), light, dark))
                painter.setPen(QPen(light.lighter(130), 1.4))
                painter.drawPath(segment)

        # Programmed toolpath.
        if program.segs:
            painter.setPen(QPen(colors["toolpath"], 1.5, Qt.PenStyle.DashLine))
            for seg in program.segs:
                a = self._transform(seg.z0, seg.r0)
                b = self._transform(seg.z1, seg.r1)
                painter.drawLine(a, b)

        # Tool is shown above the stock; X is diameter programmed.
        tip = self._transform(self.engine.tool_z, self.engine.tool_x / 2.0)
        station = _tool_station(self._active_tool())
        style = tool_styles(self.tool_assignments).get(station, DEFAULT_TOOL_STYLE)
        self._draw_tool_icon(painter, colors, tip, style)
        painter.setPen(colors["readout_text"])
        painter.setFont(QFont("Consolas", 9))
        painter.drawText(16, 24, f"X {self.engine.tool_x:8.3f}   Z {self.engine.tool_z:8.3f}")

        self._draw_origin(painter, colors)

    def _active_tool(self) -> str:
        seg = self.engine.current_seg
        if seg:
            return seg.tool
        program = self.engine.program
        if program and program.segs:
            return program.segs[-1].tool
        return "T00"

    def _draw_tool_icon(self, painter: QPainter, colors: dict[str, QColor], tip: QPointF, style: str) -> None:
        body = self._cylinder_gradient(
            QRectF(tip.x() - 10, tip.y() - 34, 20, 34), colors["tool_body_light"], colors["tool_body_dark"]
        )
        insert = self._cylinder_gradient(
            QRectF(tip.x() - 8, tip.y() - 10, 16, 10), colors["tool_light"], colors["tool_dark"]
        )
        painter.setPen(QPen(colors["tool_outline"], 1.6))

        if style == "drill":
            # Horizontal twist drill. The point at the left is the programmed
            # position and the shank extends away from the workpiece.
            shank = QRectF(tip.x() + 78, tip.y() - 9, 54, 18)
            shank_fill = self._cylinder_gradient(
                shank, colors["drill_shank_light"], colors["drill_shank_dark"]
            )
            painter.setPen(QPen(colors["general_tool_outline"], 1.0))
            painter.setBrush(shank_fill)
            painter.drawRoundedRect(shank, 5, 5)

            drill_body = QPainterPath()
            drill_body.moveTo(tip)
            drill_body.lineTo(tip + QPointF(5, -9))
            drill_body.cubicTo(
                tip + QPointF(19, -10), tip + QPointF(22, -7), tip + QPointF(31, -8)
            )
            drill_body.cubicTo(
                tip + QPointF(45, -10), tip + QPointF(59, -9), tip + QPointF(79, -9)
            )
            drill_body.lineTo(tip + QPointF(79, 9))
            drill_body.cubicTo(
                tip + QPointF(62, 9), tip + QPointF(48, 10), tip + QPointF(34, 8)
            )
            drill_body.cubicTo(
                tip + QPointF(23, 7), tip + QPointF(18, 10), tip + QPointF(5, 9)
            )
            drill_body.closeSubpath()
            flute_fill = self._cylinder_gradient(
                drill_body.boundingRect(), colors["drill_flute_light"], colors["drill_flute_dark"]
            )
            painter.setBrush(flute_fill)
            painter.drawPath(drill_body)

            # Bright helical lands clipped inside the drill silhouette.
            painter.save()
            painter.setClipPath(drill_body)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(colors["drill_land"], 4.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            helix = QPainterPath(tip + QPointF(1, -2))
            helix.cubicTo(
                tip + QPointF(14, -10), tip + QPointF(19, 10), tip + QPointF(35, 5)
            )
            helix.cubicTo(
                tip + QPointF(48, 0), tip + QPointF(53, -8), tip + QPointF(67, -3)
            )
            helix.cubicTo(
                tip + QPointF(72, -1), tip + QPointF(76, 1), tip + QPointF(81, 1)
            )
            painter.drawPath(helix)
            second_helix = QPainterPath(tip + QPointF(9, 9))
            second_helix.cubicTo(
                tip + QPointF(19, 1), tip + QPointF(25, -9), tip + QPointF(39, -4)
            )
            second_helix.cubicTo(
                tip + QPointF(52, 1), tip + QPointF(58, 9), tip + QPointF(73, 5)
            )
            painter.drawPath(second_helix)
            painter.restore()
            return
        elif style == "boring":
            # The insert's lower-left corner is the programmed cutting point;
            # the complete bar sits above and to its right, as in the photo.
            bar = QRectF(tip.x() + 29, tip.y() - 17, 115, 14)
            bar_fill = self._cylinder_gradient(bar, colors["boring_bar_light"], colors["boring_bar_dark"])
            painter.setPen(QPen(colors["general_tool_outline"], 1.0))
            painter.setBrush(bar_fill)
            painter.drawRoundedRect(bar, 5, 5)

            # Wide black head with a swept lower edge into the round shaft.
            head = QPolygonF(
                [
                    tip + QPointF(5, -17),
                    tip + QPointF(32, -17),
                    tip + QPointF(32, -7),
                    tip + QPointF(27, -4),
                    tip + QPointF(22, 1),
                    tip + QPointF(16, 3),
                    tip + QPointF(1, 2),
                ]
            )
            painter.drawPolygon(head)

            # Collar line between the two shaft sections.
            painter.setPen(QPen(colors["general_tool_outline"], 0.8))
            painter.drawLine(QPointF(tip.x() + 58, tip.y() - 17), QPointF(tip.x() + 58, tip.y() - 3))

            # Large tilted square carbide insert from the close-up reference.
            boring_insert = QPolygonF(
                [
                    tip,
                    tip + QPointF(5, -15),
                    tip + QPointF(21, -15),
                    tip + QPointF(17, 1),
                ]
            )
            insert_fill = self._cylinder_gradient(
                boring_insert.boundingRect(), colors["boring_pocket_light"], colors["boring_pocket_dark"]
            )
            painter.setPen(QPen(colors["general_tool_outline"], 1.0))
            painter.setBrush(insert_fill)
            painter.drawPolygon(boring_insert)

            screw = tip + QPointF(11, -7)
            painter.setPen(QPen(colors["general_tool_outline"], 0.8))
            painter.setBrush(colors["boring_bar_dark"])
            painter.drawEllipse(screw, 4.2, 4.2)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colors["boring_screw"])
            painter.drawEllipse(screw, 1.3, 1.3)
            return
        elif style == "grooving":
            blade = QRectF(tip.x() - 4, tip.y() - 30, 8, 24)
            painter.setBrush(body)
            painter.drawRect(blade)
            painter.setBrush(insert)
            painter.drawRect(QRectF(tip.x() - 5, tip.y() - 6, 10, 6))
        else:
            # General OD tool, traced from the supplied reference: the shank
            # and angled lower holder are one continuous silhouette.
            holder = QPolygonF(
                [
                    tip + QPointF(9, -90),
                    tip + QPointF(27, -90),
                    tip + QPointF(27, -8),
                    tip,
                    tip + QPointF(9, -27),
                ]
            )
            holder_bounds = holder.boundingRect()
            holder_fill = self._cylinder_gradient(
                holder_bounds, colors["tool_body_light"], colors["tool_body_dark"]
            )
            painter.setPen(QPen(colors["general_tool_outline"], 1.2))
            painter.setBrush(holder_fill)
            painter.drawPolygon(holder)

            # The insert overlays the sloping holder face and shares the
            # reference's narrow, skewed diamond proportions.
            insert_shape = QPolygonF(
                [
                    tip,
                    tip + QPointF(7, -17),
                    tip + QPointF(20, -21),
                    tip + QPointF(15, -6),
                ]
            )
            insert_fill = self._cylinder_gradient(
                insert_shape.boundingRect(), colors["insert_light"], colors["insert_dark"]
            )
            painter.setPen(QPen(colors["general_tool_outline"], 1.2))
            painter.setBrush(insert_fill)
            painter.drawPolygon(insert_shape)
            return

        painter.setBrush(colors["tool_light"])
        painter.drawEllipse(tip, 2.5, 2.5)

    def _draw_drawing(self, painter: QPainter, colors: dict[str, QColor]) -> None:
        program = self.engine.program
        assert program
        stock = self._stock_path(self.engine.final_stock)
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
        self._draw_origin(painter, colors)

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
