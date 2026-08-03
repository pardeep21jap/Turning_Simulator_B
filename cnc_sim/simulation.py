"""Playback engine driving lathe_core's compiled segments against a live Stock."""

from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .lathe_core import Seg, Stock
from .models import Program

RAPID_MULT = 2.5          # rapids travel this much faster than feed moves
BASE_SPEED = 14.0         # mm of tool path per second at speed 1.0


class SimulationEngine(QObject):
    changed = pyqtSignal()
    line_changed = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self.program: Program | None = None
        self.live_stock: Stock | None = None
        self.final_stock: Stock | None = None
        self.seg_i = 0
        self.seg_t = 0.0
        self.speed = 1.0
        self.tool_x = 60.0
        self.tool_z = 5.0
        self.cur_g = 0
        self.feed = 0.0
        self.current_seg: Seg | None = None

    @property
    def segs(self) -> list[Seg]:
        return self.program.segs if self.program else []

    def load(self, program: Program) -> None:
        self.pause()
        self.program = program
        st = program.stock
        self.live_stock = Stock(st.diameter, st.length, st.face_z, st.step)
        self.final_stock = Stock(st.diameter, st.length, st.face_z, st.step)
        for s in program.segs:
            self.final_stock.carve(s.z0, s.r0, s.z1, s.r1)

        self.seg_i, self.seg_t = 0, 0.0
        self.current_seg = None
        self.cur_g, self.feed = 0, 0.0
        first = program.segs[0] if program.segs else None
        self.tool_x = first.r0 * 2.0 if first else st.diameter + 10.0
        self.tool_z = first.z0 if first else 5.0
        self.changed.emit()
        if first:
            self.line_changed.emit(first.line)

    def play(self) -> None:
        if self.seg_i < len(self.segs):
            self.timer.start()

    def pause(self) -> None:
        self.timer.stop()

    def reset(self) -> None:
        if self.program:
            self.load(self.program)

    def set_speed(self, value: float) -> None:
        self.speed = max(0.1, min(10.0, value))

    def single_block(self) -> None:
        self.pause()
        segs = self.segs
        if self.seg_i >= len(segs):
            return
        line = segs[self.seg_i].line
        guard = 0
        while self.seg_i < len(segs) and segs[self.seg_i].line == line and guard < 5000:
            guard += 1
            self.advance(segs[self.seg_i].length - self.seg_t + 1e-6)
        self.changed.emit()

    def advance(self, budget: float) -> None:
        """Consume `budget` mm of tool path, cutting as we go."""
        segs = self.segs
        stock = self.live_stock
        while budget > 0 and self.seg_i < len(segs):
            s = segs[self.seg_i]
            mult = RAPID_MULT if s.rapid else 1.0
            length = s.length
            take = min(length - self.seg_t, budget * mult)
            t0, t1 = self.seg_t, min(length, self.seg_t + take)

            def at(u: float) -> tuple[float, float]:
                f = (u / length) if length else 1.0
                return s.z0 + (s.z1 - s.z0) * f, s.r0 + (s.r1 - s.r0) * f

            az, ar = at(t0)
            bz, br = at(t1)
            if stock is not None:
                stock.carve(az, ar, bz, br)

            self.tool_z, self.tool_x = bz, br * 2.0
            self.cur_g, self.feed, self.current_seg = s.g, s.feed, s
            self.line_changed.emit(s.line)

            budget -= take / mult
            self.seg_t = t1
            if self.seg_t >= length - 1e-9:
                self.seg_i += 1
                self.seg_t = 0.0

        if self.seg_i >= len(segs) and self.timer.isActive():
            self.pause()
            self.finished.emit()

    def _tick(self) -> None:
        if self.seg_i >= len(self.segs):
            self.pause()
            self.finished.emit()
            return
        self.advance(0.033 * BASE_SPEED * self.speed)
        self.changed.emit()

    def removed_fraction(self) -> float:
        return self.live_stock.removed_fraction() if self.live_stock else 0.0
