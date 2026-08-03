"""Adapter from the app's old FanucParser interface onto lathe_core.compile_program."""

from __future__ import annotations

from .lathe_core import Stock, compile_program, profile_features
from .models import Program


class FanucParser:
    def parse(
        self,
        text: str,
        stock_diameter: float = 50.0,
        stock_length: float = 100.0,
        flip_arcs: bool = False,
    ) -> Program:
        stock = Stock(stock_diameter, stock_length, 0.0)
        result = compile_program(text, stock, flip_arcs)
        features = profile_features(result.part_profile)
        return Program(
            lines=result.lines,
            segs=result.segs,
            msgs=result.msgs,
            cycle_lines=result.cycle_lines,
            part_profile=result.part_profile,
            stock=stock,
            features=features,
        )
