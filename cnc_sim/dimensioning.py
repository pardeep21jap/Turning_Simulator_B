"""Derives technical-drawing dimensions (diameters, lengths, radii) from the
finished contour lathe_core already computed for a compiled program.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .models import Program

RADIUS_TOLERANCE = 0.025
DIAMETER_TOLERANCE = 0.05


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


def extract_dimensions(program: Program) -> DimensionSet:
    diameters: list[DiameterDim] = []
    lengths: list[LengthDim] = []
    radii: list[RadiusDim] = []

    for feature in program.features:
        if feature.kind == "arc":
            radii.append(RadiusDim(z=feature.mid_z, x_radius=feature.mid_r, radius=feature.radius))
            continue
        if abs(feature.z1 - feature.z0) < 1e-6:
            continue
        if abs(feature.r1 - feature.r0) < RADIUS_TOLERANCE:
            diameter = round(feature.r0 + feature.r1, 3)
            diameters.append(DiameterDim(feature.z0, feature.z1, diameter))
            lengths.append(LengthDim(feature.z0, feature.z1))

    deduped: list[DiameterDim] = []
    for dim in diameters:
        if (
            deduped
            and abs(deduped[-1].diameter - dim.diameter) < DIAMETER_TOLERANCE
            and math.isclose(deduped[-1].z_end, dim.z_start, abs_tol=1e-3)
        ):
            deduped[-1] = DiameterDim(deduped[-1].z_start, dim.z_end, deduped[-1].diameter)
        else:
            deduped.append(dim)

    return DimensionSet(deduped, lengths, radii, [])
