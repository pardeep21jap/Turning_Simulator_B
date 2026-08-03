"""Playback engine and approximate radial stock-removal model."""

from __future__ import annotations

import math

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .models import Motion, MotionKind, Program


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
        self.motion_index = 0
        self.progress = 0.0
        self.speed = 1.0
        self.tool_x = 60.0
        self.tool_z = 5.0
        self.stock_profile: list[float] = []
        self.final_profile: list[float] = []
        self.profile_step = 0.5

    @property
    def current_motion(self) -> Motion | None:
        if self.program and 0 <= self.motion_index < len(self.program.motions):
            return self.program.motions[self.motion_index]
        return None

    def load(self, program: Program) -> None:
        self.pause()
        self.program = program
        self.motion_index = 0
        self.progress = 0.0
        first = program.motions[0] if program.motions else None
        self.tool_x = first.start_x if first else program.stock_diameter + 10
        self.tool_z = first.start_z if first else 5
        count = max(2, int(program.stock_length / self.profile_step) + 1)
        self.stock_profile = [program.stock_diameter] * count
        self.final_profile = [program.stock_diameter] * count
        for finished_motion in program.motions:
            self._apply_cut_to(self.final_profile, finished_motion, 0.0, 1.0)
        self.changed.emit()
        if first:
            self.line_changed.emit(first.line_index)

    def play(self) -> None:
        if self.current_motion:
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
        motion = self.current_motion
        if not motion:
            return
        self._apply_cut(motion, 0.0, 1.0)
        self.tool_x, self.tool_z = motion.end_x, motion.end_z
        self.motion_index += 1
        self.progress = 0.0
        self._announce_motion()
        self.changed.emit()

    def _tick(self) -> None:
        motion = self.current_motion
        if not motion:
            self.pause()
            self.finished.emit()
            return
        distance = math.hypot(motion.end_z - motion.start_z, (motion.end_x - motion.start_x) / 2.0)
        increment = self.speed * 0.9 / max(distance, 1.0)
        old_progress = self.progress
        self.progress = min(1.0, self.progress + increment)
        eased = self.progress
        self.tool_x = motion.start_x + (motion.end_x - motion.start_x) * eased
        self.tool_z = motion.start_z + (motion.end_z - motion.start_z) * eased
        self._apply_cut(motion, old_progress, self.progress)
        if self.progress >= 1.0:
            self.motion_index += 1
            self.progress = 0.0
            self._announce_motion()
        self.changed.emit()

    def _announce_motion(self) -> None:
        motion = self.current_motion
        if motion:
            self.line_changed.emit(motion.line_index)

    def _apply_cut(self, motion: Motion, p0: float, p1: float) -> None:
        if not self.program:
            return
        self._apply_cut_to(self.stock_profile, motion, p0, p1)

    def _apply_cut_to(self, profile: list[float], motion: Motion, p0: float, p1: float) -> None:
        if not motion.is_cutting:
            return
        span = max(abs(motion.end_z - motion.start_z), abs(motion.end_x - motion.start_x), 0.5)
        samples = max(2, int(span / self.profile_step) + 2)
        for i in range(samples + 1):
            p = p0 + (p1 - p0) * i / samples
            z = motion.start_z + (motion.end_z - motion.start_z) * p
            x = motion.start_x + (motion.end_x - motion.start_x) * p
            index = int(round(-z / self.profile_step))
            if 0 <= index < len(profile):
                profile[index] = min(profile[index], max(0.0, x))
                if motion.kind in (MotionKind.CUT, MotionKind.THREAD):
                    for neighbor in (-1, 1):
                        ni = index + neighbor
                        if 0 <= ni < len(profile):
                            profile[ni] = min(profile[ni], max(0.0, x + 0.2))
