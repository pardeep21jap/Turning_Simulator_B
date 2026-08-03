"""Derives technical-drawing dimensions (diameters, lengths, radii, chamfers)
from the finished contour of a parsed program.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .models import Motion, MotionKind, Program

DIAMETER_TOLERANCE = 0.05
CHAMFER_ANGLE_TOLERANCE = 6.0


@dataclass(slots=True)
class DiameterDim:
    z_start: float
    z_end: float
    diameter: float


@dataclass(slots=True)
class LengthDim:
    z_start: float
    z_end: float

    @property
    def length(self) -> float:
        return abs(self.z_end - self.z_start)


@dataclass(slots=True)
class RadiusDim:
    z: float
    x_radius: float
    radius: float


@dataclass(slots=True)
class ChamferDim:
    z: float
    x_radius: float
    leg: float
    angle: float


@dataclass(slots=True)
class DimensionSet:
    diameters: list[DiameterDim]
    lengths: list[LengthDim]
    radii: list[RadiusDim]
    chamfers: list[ChamferDim]


def _finish_contour(program: Program) -> list[Motion]:
    cycles = {m.cycle for m in program.motions if m.cycle}
    if "G70" in cycles:
        wanted = {"G70"}
    elif cycles & {"G71", "G72"}:
        wanted = {"G71", "G72"}
    else:
        wanted = {None}
    return [m for m in program.motions if m.cycle in wanted and m.kind != MotionKind.RAPID]


def extract_dimensions(program: Program) -> DimensionSet:
    diameters: list[DiameterDim] = []
    lengths: list[LengthDim] = []
    radii: list[RadiusDim] = []
    chamfers: list[ChamferDim] = []

    for motion in _finish_contour(program):
        dz = motion.end_z - motion.start_z
        dx = motion.end_x - motion.start_x

        if motion.kind in (MotionKind.ARC_CW, MotionKind.ARC_CCW):
            if motion.arc_radius:
                radii.append(
                    RadiusDim(
                        z=(motion.start_z + motion.end_z) / 2.0,
                        x_radius=(motion.start_x + motion.end_x) / 4.0,
                        radius=motion.arc_radius,
                    )
                )
            continue

        if abs(dz) < 1e-6:
            continue

        if abs(dx) < DIAMETER_TOLERANCE * 2:
            diameter = round((motion.start_x + motion.end_x) / 2.0, 3)
            diameters.append(DiameterDim(motion.start_z, motion.end_z, diameter))
            lengths.append(LengthDim(motion.start_z, motion.end_z))
            continue

        angle = math.degrees(math.atan2(abs(dx) / 2.0, abs(dz)))
        if abs(angle - 45.0) <= CHAMFER_ANGLE_TOLERANCE:
            leg = min(abs(dz), abs(dx) / 2.0)
            chamfers.append(
                ChamferDim(
                    z=(motion.start_z + motion.end_z) / 2.0,
                    x_radius=max(motion.start_x, motion.end_x) / 2.0,
                    leg=leg,
                    angle=45.0,
                )
            )

    deduped: list[DiameterDim] = []
    for dim in diameters:
        if deduped and abs(deduped[-1].diameter - dim.diameter) < DIAMETER_TOLERANCE and math.isclose(
            deduped[-1].z_end, dim.z_start, abs_tol=1e-3
        ):
            deduped[-1] = DiameterDim(deduped[-1].z_start, dim.z_end, deduped[-1].diameter)
        else:
            deduped.append(dim)

    return DimensionSet(deduped, lengths, radii, chamfers)
