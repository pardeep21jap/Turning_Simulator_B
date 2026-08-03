"""
lathe_core - G-code parsing, canned-cycle expansion and material removal
for a 2D turning simulator.

No GUI dependencies. Everything here is plain Python, so the same module
backs the Tkinter front-end, a Qt front-end, a batch verifier, or a test
suite. Only the drawing code needs rewriting per toolkit.

Coordinate convention
---------------------
Z runs along the spindle axis, positive toward the tailstock (to the right
on screen). X is programmed as a DIAMETER; internally everything is a
RADIUS. Arcs are drawn in the common screen-view convention: G02 appears
clockwise on screen, G03 counter-clockwise. Set flip_arcs=True to swap
them when needed.
"""

from __future__ import annotations

import math
import re
from array import array
from dataclasses import dataclass, field

WORD_RE = re.compile(r"([A-Z])\s*([+-]?(?:\d+\.?\d*|\.\d+))")
COMMENT_RE = re.compile(r"\([^)]*\)")


# --------------------------------------------------------------------------
# lexing
# --------------------------------------------------------------------------
def parse_words(raw: str) -> dict:
    """Split one block into address words. G and M collect into lists."""
    text = COMMENT_RE.sub(" ", raw).split(";")[0].upper()
    out: dict = {"G": [], "M": []}
    for letter, value in WORD_RE.findall(text):
        v = float(value)
        if letter == "G":
            out["G"].append(int(round(v)))
        elif letter == "M":
            out["M"].append(int(round(v)))
        else:
            out[letter] = v
    return out


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------
def arc_points(z0, r0, z1, r1, radius, ccw_on_screen, chord=0.12):
    """Flatten an R-format arc into points. Returns None if unrealisable."""
    d = math.hypot(z1 - z0, r1 - r0)
    ar = abs(radius)
    if ar <= 0 or d < 1e-9 or d > 2 * ar + 1e-4:
        return None
    h = math.sqrt(max(0.0, ar * ar - d * d / 4.0))
    if radius < 0:                      # negative R selects the major arc
        h = -h
    mz, mr = (z0 + z1) / 2.0, (r0 + r1) / 2.0
    uz, ur = (z1 - z0) / d, (r1 - r0) / d
    lz, lr = -ur, uz                    # left-hand normal of travel
    sign = 1.0 if ccw_on_screen else -1.0
    cz, cr = mz + sign * h * lz, mr + sign * h * lr

    a0 = math.atan2(r0 - cr, z0 - cz)
    a1 = math.atan2(r1 - cr, z1 - cz)
    if ccw_on_screen:
        while a1 <= a0:
            a1 += 2 * math.pi
    else:
        while a1 >= a0:
            a1 -= 2 * math.pi

    steps = max(6, int(math.ceil(abs(a1 - a0) * ar / chord)))
    pts = []
    for k in range(1, steps + 1):
        a = a0 + (a1 - a0) * k / steps
        pts.append((cz + ar * math.cos(a), cr + ar * math.sin(a)))
    return pts


# --------------------------------------------------------------------------
# stock model
# --------------------------------------------------------------------------
class Stock:
    """
    Bar stock as a 1-D field of radii sampled along Z.

    Turning only ever removes material from the outside inward, so one
    radius per Z column is enough to describe the part exactly. A cut sets
    each column it spans to min(current, tool radius).
    """

    def __init__(self, diameter=45.0, length=55.0, face_z=0.0, step=0.05):
        self.diameter = float(diameter)
        self.length = float(length)
        self.face_z = float(face_z)
        self.step = float(step)
        self.zmin = self.face_z - self.length - 30.0
        self.zmax = self.face_z + 25.0
        self.n = int(round((self.zmax - self.zmin) / self.step)) + 1
        self.reset()

    # -- indexing ---------------------------------------------------------
    def idx(self, z: float) -> int:
        return int(round((z - self.zmin) / self.step))

    def z_at(self, i: int) -> float:
        return self.zmin + i * self.step

    @property
    def radius(self) -> float:
        return self.diameter / 2.0

    # -- state ------------------------------------------------------------
    def reset(self) -> None:
        r = self.radius
        self.rad = array("f", [0.0]) * self.n
        self.cut = bytearray(self.n)
        left = self.face_z - self.length
        for i in range(self.n):
            z = self.z_at(i)
            if left - 1e-9 <= z <= self.face_z + 1e-9:
                self.rad[i] = r
        self._area0 = sum(v * v for v in self.rad) or 1.0

    # -- cutting ----------------------------------------------------------
    def _column(self, i: int, r: float) -> None:
        if 0 <= i < self.n and r < self.rad[i]:
            self.rad[i] = max(0.0, r)
            self.cut[i] = 1

    def carve(self, z0, r0, z1, r1) -> None:
        """Sweep the tool tip along a straight move, removing material."""
        if abs(z1 - z0) < self.step:
            self._column(self.idx(z1), min(r0, r1))
            return
        a, b = self.idx(min(z0, z1)), self.idx(max(z0, z1))
        dz = z1 - z0
        for i in range(max(0, a), min(self.n - 1, b) + 1):
            t = (self.z_at(i) - z0) / dz
            self._column(i, r0 + (r1 - r0) * min(1.0, max(0.0, t)))

    def removed_fraction(self) -> float:
        return max(0.0, 1.0 - sum(v * v for v in self.rad) / self._area0)

    def profile(self):
        """[(z, radius), ...] for every column that still has material."""
        return [(self.z_at(i), self.rad[i]) for i in range(self.n) if self.rad[i] > 0]


# --------------------------------------------------------------------------
# compiled output
# --------------------------------------------------------------------------
@dataclass
class Seg:
    z0: float
    r0: float
    z1: float
    r1: float
    rapid: bool
    line: int
    g: int
    feed: float
    tool: str = "T00"
    css: float = 0.0
    clamp: float = 4000.0
    sval: float = 0.0
    arc_radius: float = 0.0   # 0 for lines; |R| for arc chords, used for drawing dimensions

    @property
    def length(self) -> float:
        return math.hypot(self.z1 - self.z0, self.r1 - self.r0)


@dataclass
class Message:
    kind: str          # 'ok' | 'err'
    line: int          # zero-based source line
    text: str


@dataclass
class CompileResult:
    segs: list = field(default_factory=list)
    msgs: list = field(default_factory=list)
    lines: list = field(default_factory=list)
    cycle_lines: set = field(default_factory=set)
    part_profile: list = field(default_factory=list)


# --------------------------------------------------------------------------
# compiler
# --------------------------------------------------------------------------
class Compiler:
    """Turns a program into a flat list of straight-line tool moves."""

    def __init__(self, text: str, stock: Stock, flip_arcs: bool = False):
        self.text = text
        self.stock = stock
        self.flip = flip_arcs

        self.lines = text.splitlines()
        self.blocks = [(i, parse_words(s)) for i, s in enumerate(self.lines)]
        self.by_n = {}
        for i, w in self.blocks:
            if "N" in w:
                self.by_n[int(w["N"])] = i

        self.out: list[Seg] = []
        self.msgs: list[Message] = []
        self.cycle_lines: set[int] = set()
        self.part_profile: list[Seg] = []

        # modal machine state
        self.z = 0.0
        self.x = 0.0          # diameter
        self.g = 0
        self.f = 0.0
        self.absolute = True
        self.tool = "T00"
        self.css = 0.0
        self.clamp = 4000.0
        self.sval = 0.0
        self.cyc_u = 2.0      # G71 depth of cut (radius)
        self.cyc_r = 0.5      # G71 retract
        self.cyc_g74_r = 0.5  # G74 retract between pecks

    # -- helpers ----------------------------------------------------------
    def say(self, kind, line, text):
        if not any(m.line == line and m.text == text for m in self.msgs):
            self.msgs.append(Message(kind, line, text))

    def seg(self, z0, r0, z1, r1, rapid, line, g, feed, arc_radius=0.0) -> Seg:
        return Seg(z0, r0, z1, r1, rapid, line, g, feed,
                   self.tool, self.css, self.clamp, self.sval, arc_radius)

    def move(self, words, g, tz, tr, feed, line):
        """Emit one motion, splitting arcs into chords."""
        z0, r0 = self.z, self.x / 2.0
        if g in (2, 3):
            ccw = (g == 3)
            if self.flip:
                ccw = not ccw
            radius = words.get("R")
            if radius is None and ("I" in words or "K" in words):
                cz = z0 + words.get("K", 0.0)
                cr = r0 + words.get("I", 0.0) / 2.0
                radius = math.hypot(z0 - cz, r0 - cr)
            pts = arc_points(z0, r0, tz, tr, radius, ccw) if radius else None
            if pts is None:
                self.say("err", line,
                         "arc without R / I,K - cut as a straight line"
                         if radius is None else
                         "arc radius too small for the end point - cut straight")
                self.out.append(self.seg(z0, r0, tz, tr, False, line, g, feed))
            else:
                pz, pr = z0, r0
                for az, ar in pts:
                    self.out.append(self.seg(pz, pr, az, ar, False, line, g, feed,
                                             arc_radius=abs(radius)))
                    pz, pr = az, ar
        else:
            self.out.append(self.seg(z0, r0, tz, tr, g == 0, line, g, feed))
        self.z, self.x = tz, tr * 2.0

    def run_range(self, a, b, feed_override=None, sink=None):
        """Execute blocks a..b as ordinary motion. sink diverts the output."""
        mark = len(self.out)
        for k in range(a, b + 1):
            w = self.blocks[k][1]
            for g in w["G"]:
                if g <= 3:
                    self.g = g
            tz = (w["Z"] if self.absolute else self.z + w["Z"]) if "Z" in w else self.z
            tx = (w["X"] if self.absolute else self.x + w["X"]) if "X" in w else self.x
            if "F" in w:
                self.f = w["F"]
            if "X" in w or "Z" in w:
                self.move(w, self.g, tz, tx / 2.0,
                          self.f if feed_override is None else feed_override, k)
        if sink is not None:
            sink.extend(self.out[mark:])
            del self.out[mark:]

    def g28_return(self, words, line):
        """Approximate G28 return to reference using a rapid move to X0 Z0."""
        tz = self.z + words.get("W", 0.0) if "W" in words else self.z
        tx = self.x + words.get("U", 0.0) if "U" in words else self.x
        if "X" in words:
            tx = words["X"] if self.absolute else self.x + words["X"]
        if "Z" in words:
            tz = words["Z"] if self.absolute else self.z + words["Z"]

        if abs(tz - self.z) > 1e-9 or abs(tx - self.x) > 1e-9:
            self.out.append(self.seg(self.z, self.x / 2.0, tz, tx / 2.0,
                                     True, line, 0, 0.0))
            self.z, self.x = tz, tx

        if abs(self.z) > 1e-9 or abs(self.x) > 1e-9:
            self.out.append(self.seg(self.z, self.x / 2.0, 0.0, 0.0,
                                     True, line, 0, 0.0))
            self.z, self.x = 0.0, 0.0

    def g74_peck(self, words, line):
        """Simple Z-axis peck drilling / grooving cycle for turning programs."""
        target_z = words.get("Z", self.z)
        feed = words.get("F", self.f)
        peck = words.get("Q", 0.0)
        peck = peck / 1000.0 if peck > 100.0 else peck
        peck = max(0.1, abs(peck))
        retract = max(0.05, self.cyc_g74_r)
        x_dia = words.get("X", self.x)
        x_rad = x_dia / 2.0

        if abs(x_dia - self.x) > 1e-9:
            self.out.append(self.seg(self.z, self.x / 2.0, self.z, x_rad,
                                     True, line, 0, 0.0))
            self.x = x_dia

        z = self.z
        passes = 0
        while z > target_z + 1e-9 and passes < 1000:
            next_z = max(target_z, z - peck)
            self.move({}, 1, next_z, x_rad, feed, line)
            z = self.z
            passes += 1
            if z > target_z + 1e-9:
                self.out.append(self.seg(self.z, self.x / 2.0, z + retract, x_rad,
                                         True, line, 0, 0.0))
                self.z = z + retract

        self.say("ok", line,
                 f"G74 expanded - {passes} pecks, {peck:.2f} mm step")

    # -- G71 / G73 stock removal -----------------------------------------
    def rough(self, p_block, q_block, u, w_off, feed, line, cycle_name="G71"):
        z_save, x_save = self.z, self.x
        profile: list[Seg] = []
        self.run_range(p_block, q_block, feed, sink=profile)
        self.z, self.x = z_save, x_save
        if not profile:
            self.say("err", line, f"{cycle_name} profile is empty")
            return

        # The block at P only approaches the shape; the shape starts at its
        # end point.
        start_z, start_r = profile[0].z1, profile[0].r1
        body = profile[1:]
        if not self.part_profile and body:
            self.part_profile = list(body)

        st = self.stock
        table = array("f", [-1.0]) * st.n
        z_hi = z_lo = start_z + w_off
        r_min = start_r + u / 2.0

        def put(z, r):
            i = st.idx(z)
            if 0 <= i < st.n and r > table[i]:
                table[i] = r

        put(start_z + w_off, start_r + u / 2.0)
        for s in body:
            steps = max(2, int(math.ceil(s.length / st.step)) + 1)
            for k in range(steps + 1):
                t = k / steps
                z = s.z0 + (s.z1 - s.z0) * t + w_off
                r = s.r0 + (s.r1 - s.r0) * t + u / 2.0
                put(z, r)
                z_hi, z_lo, r_min = max(z_hi, z), min(z_lo, z), min(r_min, r)

        for i in range(st.idx(z_lo), st.idx(z_hi) + 1):
            if 0 <= i < st.n and table[i] < 0:
                table[i] = table[i - 1] if i > 0 and table[i - 1] >= 0 else r_min

        def profile_r(z):
            i = st.idx(z)
            return table[i] if 0 <= i < st.n else -1.0

        # horizontal roughing passes
        clearance = max(1.0, self.cyc_r * 2)
        z_app = z_hi + clearance
        depth = max(0.05, self.cyc_u)
        r = st.radius - depth
        passes = 0
        while r > r_min - 1e-6 and passes < 400:
            z_end = z_lo
            z = z_hi
            while z >= z_lo:
                if profile_r(z) > r + 1e-6:
                    z_end = z
                    break
                z -= st.step
            self.out.append(self.seg(self.z, self.x / 2.0, z_app, r, True, line, 0, 0.0))
            self.z, self.x = z_app, r * 2.0
            self.move({}, 1, z_end, r, feed, line)                       # cut in -Z
            self.move({}, 1, z_end + self.cyc_r, r + self.cyc_r, feed, line)  # 45 deg out
            self.out.append(self.seg(self.z, self.x / 2.0, z_app,
                                     r + self.cyc_r, True, line, 0, 0.0))
            self.z, self.x = z_app, (r + self.cyc_r) * 2.0
            r -= depth
            passes += 1

        # semi-finish sweep along the offset profile
        self.out.append(self.seg(self.z, self.x / 2.0, z_app,
                                 start_r + u / 2.0, True, line, 0, 0.0))
        self.z, self.x = z_app, (start_r + u / 2.0) * 2.0
        self.move({}, 1, start_z + w_off, start_r + u / 2.0, feed, line)
        for s in body:
            self.move({}, 1, s.z1 + w_off, s.r1 + u / 2.0, feed, line)

        self.out.append(self.seg(self.z, self.x / 2.0, z_save, x_save / 2.0,
                                 True, line, 0, 0.0))
        self.z, self.x = z_save, x_save
        self.say("ok", line,
                 f"{cycle_name} expanded - {passes} roughing passes, {self.cyc_u:.2f} mm depth")

    # -- main pass --------------------------------------------------------
    def compile(self) -> CompileResult:
        pc, guard, ended = 0, 0, False
        while pc < len(self.blocks) and not ended and guard < 20000:
            guard += 1
            i, w = self.blocks[pc]
            gs = w["G"]

            if 90 in gs:
                self.absolute = True
            if 91 in gs:
                self.absolute = False
            if 96 in gs:
                self.css = w.get("S", self.css)
            if 97 in gs:
                self.css = 0.0
            if 92 in gs and "S" in w:
                self.clamp = w["S"]
            if "T" in w:
                self.tool = "T%02d" % int(round(w["T"]))
            if "S" in w and 92 not in gs and 96 not in gs:
                self.sval = w["S"]
            if "F" in w:
                self.f = w["F"]

            # ---- G28 -----------------------------------------------------
            if 28 in gs:
                self.g28_return(w, i)
                pc += 1
                continue

            # ---- G71 / G73 ----------------------------------------------
            cycle_g = 71 if 71 in gs else (73 if 73 in gs else None)
            if cycle_g is not None:
                cycle_name = f"G{cycle_g}"
                if "P" in w and "Q" in w:
                    pb = self.by_n.get(int(w["P"]))
                    qb = self.by_n.get(int(w["Q"]))
                    if pb is None or qb is None or qb < pb:
                        self.say("err", i,
                                 f"{cycle_name} P{int(w['P'])} Q{int(w['Q'])} - "
                                 "cannot find those block numbers")
                    else:
                        self.cycle_lines.update(range(pb, qb + 1))
                        self.rough(pb, qb, w.get("U", 0.0), w.get("W", 0.0),
                                   w.get("F", self.f), i, cycle_name=cycle_name)
                        pc = max(pc + 1, qb + 1)
                        continue
                else:
                    self.cyc_u = w.get("U", self.cyc_u)
                    self.cyc_r = w.get("R", self.cyc_r)
                pc += 1
                continue

            # ---- G74 -----------------------------------------------------
            if 74 in gs:
                if "R" in w and "Z" not in w and "X" not in w:
                    self.cyc_g74_r = w["R"]
                else:
                    self.g74_peck(w, i)
                pc += 1
                continue

            # ---- G70 -----------------------------------------------------
            if 70 in gs:
                pb = self.by_n.get(int(w.get("P", -1)))
                qb = self.by_n.get(int(w.get("Q", -1)))
                if pb is None or qb is None:
                    self.say("err", i, "G70 without a valid P/Q range")
                else:
                    self.cycle_lines.update(range(pb, qb + 1))
                    self.run_range(pb, qb, w.get("F", self.f))
                    self.say("ok", i, "G70 finishing pass")
                pc += 1
                continue

            # ---- ordinary motion ----------------------------------------
            for g in gs:
                if g <= 3:
                    self.g = g
            tz = (w["Z"] if self.absolute else self.z + w["Z"]) if "Z" in w else self.z
            tx = (w["X"] if self.absolute else self.x + w["X"]) if "X" in w else self.x
            if "X" in w or "Z" in w:
                self.move(w, self.g, tz, tx / 2.0, self.f, i)

            if 30 in w["M"] or 2 in w["M"]:
                ended = True
            pc += 1

        if not ended:
            self.say("err", max(0, len(self.lines) - 1),
                     "no M30 / M02 - program end assumed")
        if not self.part_profile:
            self.part_profile = [s for s in self.out if not s.rapid and s.g in (1, 2, 3)]
        return CompileResult(self.out, self.msgs, self.lines, self.cycle_lines,
                             self.part_profile)


def compile_program(text, stock, flip_arcs=False) -> CompileResult:
    return Compiler(text, stock, flip_arcs).compile()


# --------------------------------------------------------------------------
# dimensioned drawing support
# --------------------------------------------------------------------------
@dataclass
class Feature:
    """One line or arc of the finished-part outline, for a dimensioned print."""
    kind: str          # 'line' | 'arc'
    z0: float
    r0: float
    z1: float
    r1: float
    radius: float = 0.0    # arc radius (kind == 'arc')
    mid_z: float = 0.0     # a point on the arc, for the R-leader
    mid_r: float = 0.0


def profile_features(part_profile):
    """Collapse a chain of Segs (arcs already chorded into several Segs that
    share one arc_radius) back into whole line/arc features for dimensioning."""
    feats = []
    i, n = 0, len(part_profile)
    while i < n:
        s = part_profile[i]
        if s.arc_radius > 0:
            j = i
            zs, rs = [s.z0], [s.r0]
            while j < n and part_profile[j].arc_radius == s.arc_radius:
                zs.append(part_profile[j].z1)
                rs.append(part_profile[j].r1)
                j += 1
            mid = len(zs) // 2
            feats.append(Feature("arc", zs[0], rs[0], zs[-1], rs[-1],
                                 radius=s.arc_radius, mid_z=zs[mid], mid_r=rs[mid]))
            i = j
        else:
            feats.append(Feature("line", s.z0, s.r0, s.z1, s.r1))
            i += 1
    return feats


def spindle_rpm(diameter, css, clamp, fixed_rpm):
    """Surface speed in m/min -> rpm at the current diameter, clamped."""
    d = max(0.5, diameter)
    if css:
        return min(clamp, 1000.0 * css / (math.pi * d))
    return fixed_rpm or 0.0


DEFAULT_PROGRAM = """O1010
N10 G18 G21 G95 G90
N12 T00 M6
N16 G54 S1146 M4
N18 G18 G0 G90 G94 X50. Z30.
N20 G92 S1500
N22 G96 S180 M4
N24 Z25.
N26 G71 U2. R0.3
N28 G71 P32 Q34 U1. W0.5 F0.7
N32 G1 X16 Z0.25
X20. Z-2
Z-15
G3 X30. Z-20.5 R5
G1 Z-30
G2 X38 Z-34.
N34 G1 X43.
N38 G0 X50. Z20
N46 Z2
N50 G70 P32 Q34 F0.3
N60 G0 X50. Z20
N64 M5
N66 M30"""
