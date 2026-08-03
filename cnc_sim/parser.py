"""Small, defensive FANUC-style parser used by the simulator."""

from __future__ import annotations

import math
import re

from .models import Alarm, Block, Motion, MotionKind, Program

WORD_RE = re.compile(r"([A-Z])\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))", re.I)
PAREN_COMMENT_RE = re.compile(r"\([^)]*\)")
SUPPORTED_G = {0, 1, 2, 3, 18, 20, 21, 28, 40, 50, 70, 71, 72, 76, 80, 90, 91, 94, 95, 96, 97, 98, 99}


class FanucParser:
    def parse(self, text: str, stock_diameter: float = 50.0, stock_length: float = 100.0) -> Program:
        blocks: list[Block] = []
        alarms: list[Alarm] = []
        for index, raw in enumerate(text.splitlines()):
            clean = PAREN_COMMENT_RE.sub("", raw.split(";", 1)[0]).strip().upper()
            if not clean or clean == "%":
                continue
            words: dict[str, list[float]] = {}
            for letter, number in WORD_RE.findall(clean):
                words.setdefault(letter, []).append(float(number))
            residue = WORD_RE.sub("", clean).replace("%", "").strip()
            if residue:
                alarms.append(Alarm(index, "PS001", f"Unrecognized text: {residue}", "error"))
            block = Block(
                line_index=index,
                raw=raw,
                words=words,
                g_codes=[int(round(v)) for v in words.get("G", [])],
                m_codes=[int(round(v)) for v in words.get("M", [])],
                sequence=int(words["N"][-1]) if words.get("N") else None,
            )
            for code in block.g_codes:
                if code not in SUPPORTED_G:
                    alarms.append(Alarm(index, "PS010", f"G{code:02d} is not supported", "error"))
            blocks.append(block)

        motions = self._build_motions(blocks, alarms, stock_diameter, stock_length)
        if not blocks:
            alarms.append(Alarm(0, "PS000", "Program contains no executable blocks", "error"))
        return Program(blocks, motions, alarms, stock_diameter, stock_length)

    def _build_motions(
        self, blocks: list[Block], alarms: list[Alarm], stock_diameter: float, stock_length: float
    ) -> list[Motion]:
        motions: list[Motion] = []
        x, z = stock_diameter + 10.0, 5.0
        feed, spindle = 0.2, 0.0
        modal_motion = 0
        absolute = True
        metric_scale = 1.0
        spindle_on = False
        sequence_map = {b.sequence: i for i, b in enumerate(blocks) if b.sequence is not None}
        pending_cycle: tuple[int, Block] | None = None
        first_g76: Block | None = None

        def add_motion(block: Block, nx: float, nz: float, kind: MotionKind, cycle: str | None = None) -> None:
            nonlocal x, z
            if not all(math.isfinite(v) for v in (nx, nz)):
                alarms.append(Alarm(block.line_index, "PS011", "Coordinate is not finite", "error"))
                return
            if nx < -0.01:
                alarms.append(Alarm(block.line_index, "OT001", "Negative X diameter crosses spindle centerline", "error"))
            if nx > stock_diameter + 80 or nz > 60 or nz < -stock_length - 60:
                alarms.append(Alarm(block.line_index, "OT002", "Command exceeds educational machine travel", "error"))
            if (
                kind == MotionKind.RAPID
                and cycle is None
                and min(x, nx) < stock_diameter - 0.05
                and min(z, nz) < 0.0
                and max(z, nz) > -stock_length
            ):
                alarms.append(Alarm(block.line_index, "CL001", "Possible rapid move through uncut stock", "warning"))
            if kind != MotionKind.RAPID and not spindle_on:
                alarms.append(Alarm(block.line_index, "SP001", "Cutting move commanded while spindle is stopped", "warning"))
            motions.append(Motion(block.line_index, block.raw, x, z, nx, nz, kind, feed, spindle, cycle=cycle))
            x, z = nx, nz

        def coordinate(block: Block, axis: str, incremental_axis: str, current: float) -> float:
            direct = block.last(axis)
            incremental = block.last(incremental_axis)
            if incremental is not None:
                return current + incremental * metric_scale
            if direct is None:
                return current
            value = direct * metric_scale
            return value if absolute else current + value

        def replay_profile(cycle_block: Block, cycle_name: str) -> None:
            p = int(cycle_block.last("P", -1) or -1)
            q = int(cycle_block.last("Q", -1) or -1)
            if p not in sequence_map or q not in sequence_map or sequence_map[p] > sequence_map[q]:
                alarms.append(Alarm(cycle_block.line_index, "PS032", f"{cycle_name} requires valid P/Q sequence blocks", "error"))
                return
            for profile in blocks[sequence_map[p] : sequence_map[q] + 1]:
                profile_g = profile.g_codes[-1] if profile.g_codes else 1
                if profile_g not in (0, 1, 2, 3):
                    continue
                nx = coordinate(profile, "X", "U", x)
                nz = coordinate(profile, "Z", "W", z)
                kind = MotionKind.RAPID if profile_g == 0 and cycle_name == "G70" else MotionKind.CUT
                add_motion(profile, nx, nz, kind, cycle_name)

        for i, block in enumerate(blocks):
            if 20 in block.g_codes:
                metric_scale = 25.4
            if 21 in block.g_codes:
                metric_scale = 1.0
            if 90 in block.g_codes:
                absolute = True
            if 91 in block.g_codes:
                absolute = False
            if block.last("F") is not None:
                feed = abs(block.last("F") or feed) * metric_scale
                if feed <= 0:
                    alarms.append(Alarm(block.line_index, "FE001", "Feed must be greater than zero", "error"))
            if block.last("S") is not None:
                spindle = abs(block.last("S") or 0.0)
            if 3 in block.m_codes or 4 in block.m_codes:
                spindle_on = True
            if 5 in block.m_codes or 30 in block.m_codes:
                spindle_on = False

            cycle = next((g for g in block.g_codes if g in (70, 71, 72, 76)), None)
            if cycle in (71, 72):
                if block.last("P") is None:
                    pending_cycle = (cycle, block)
                else:
                    replay_profile(block, f"G{cycle}")
                    pending_cycle = None
                continue
            if cycle == 70:
                replay_profile(block, "G70")
                continue
            if cycle == 76:
                if first_g76 is None:
                    first_g76 = block
                else:
                    tx = coordinate(block, "X", "U", x)
                    tz = coordinate(block, "Z", "W", z)
                    depth = max(0.1, (x - tx) / 2.0)
                    passes = max(3, min(10, int(math.ceil(depth / max((block.last("Q", 200) or 200) / 1000.0, 0.1)))))
                    start_x, start_z = x, z
                    for pidx in range(1, passes + 1):
                        px = start_x - (start_x - tx) * math.sqrt(pidx / passes)
                        add_motion(block, px, start_z, MotionKind.RAPID, "G76")
                        add_motion(block, px, tz, MotionKind.THREAD, "G76")
                        add_motion(block, start_x, tz, MotionKind.RAPID, "G76")
                        add_motion(block, start_x, start_z, MotionKind.RAPID, "G76")
                    first_g76 = None
                continue

            explicit_motion = next((g for g in reversed(block.g_codes) if g in (0, 1, 2, 3)), None)
            if explicit_motion is not None:
                modal_motion = explicit_motion
            has_coordinate = any(k in block.words for k in ("X", "Z", "U", "W"))
            if not has_coordinate:
                continue
            nx = coordinate(block, "X", "U", x)
            nz = coordinate(block, "Z", "W", z)
            kind = {0: MotionKind.RAPID, 1: MotionKind.CUT, 2: MotionKind.ARC_CW, 3: MotionKind.ARC_CCW}.get(modal_motion, MotionKind.RAPID)
            add_motion(block, nx, nz, kind)
            if kind in (MotionKind.ARC_CW, MotionKind.ARC_CCW):
                motions[-1].arc_radius = abs(block.last("R", 0.0) or 0.0) or None

        if pending_cycle:
            alarms.append(Alarm(pending_cycle[1].line_index, "PS033", f"Incomplete G{pending_cycle[0]} two-block cycle", "error"))
        if first_g76:
            alarms.append(Alarm(first_g76.line_index, "PS034", "Incomplete G76 two-block cycle", "error"))
        if not motions:
            alarms.append(Alarm(0, "PS002", "No tool motion was generated", "warning"))
        return motions
