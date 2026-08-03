"""Bundles a compiled program with its stock and derived dimensioning features."""

from __future__ import annotations

from dataclasses import dataclass, field

from .lathe_core import Feature, Message, Seg, Stock


@dataclass
class Program:
    lines: list[str]
    segs: list[Seg]
    msgs: list[Message]
    cycle_lines: set[int]
    part_profile: list[Seg]
    stock: Stock
    features: list[Feature] = field(default_factory=list)

    @property
    def stock_diameter(self) -> float:
        return self.stock.diameter

    @property
    def stock_length(self) -> float:
        return self.stock.length
