"""Shared data models for parsing and simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MotionKind(str, Enum):
    RAPID = "rapid"
    CUT = "cut"
    ARC_CW = "arc_cw"
    ARC_CCW = "arc_ccw"
    THREAD = "thread"


@dataclass(slots=True)
class Alarm:
    line_index: int
    code: str
    message: str
    severity: str = "warning"


@dataclass(slots=True)
class Block:
    line_index: int
    raw: str
    words: dict[str, list[float]] = field(default_factory=dict)
    g_codes: list[int] = field(default_factory=list)
    m_codes: list[int] = field(default_factory=list)
    sequence: int | None = None

    def last(self, letter: str, default: float | None = None) -> float | None:
        values = self.words.get(letter.upper())
        return values[-1] if values else default


@dataclass(slots=True)
class Motion:
    line_index: int
    raw: str
    start_x: float
    start_z: float
    end_x: float
    end_z: float
    kind: MotionKind
    feed: float
    spindle: float
    arc_radius: float | None = None
    cycle: str | None = None

    @property
    def is_cutting(self) -> bool:
        return self.kind != MotionKind.RAPID


@dataclass(slots=True)
class Program:
    blocks: list[Block]
    motions: list[Motion]
    alarms: list[Alarm]
    stock_diameter: float = 50.0
    stock_length: float = 100.0
