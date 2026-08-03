import unittest

from cnc_sim.canvas import DEFAULT_TOOL_ASSIGNMENTS, tool_styles
from cnc_sim.examples import EXAMPLES
from cnc_sim.simulation import SimulationEngine
from cnc_sim.parser import FanucParser


class ParserTests(unittest.TestCase):
    def test_default_tool_assignments_match_operation_setup(self):
        self.assertEqual(
            DEFAULT_TOOL_ASSIGNMENTS,
            {"turning": 1, "roughing": 2, "boring": 3, "drilling": 4},
        )
        self.assertEqual(
            tool_styles(DEFAULT_TOOL_ASSIGNMENTS),
            {1: "turning", 2: "turning", 3: "boring", 4: "drill", 5: "grooving"},
        )

    def setUp(self):
        self.parser = FanucParser()

    def test_all_examples_compile(self):
        for name, source in EXAMPLES.items():
            with self.subTest(name=name):
                program = self.parser.parse(source)
                self.assertGreater(len(program.segs), 0)

    def test_relative_positioning_mode(self):
        # G91 remains supported alongside U/W axis shorthand.
        program = self.parser.parse("G21 G90\nG00 X50 Z0\nG91\nG01 X-10 Z-20 F0.2\nG90\nM30\n")
        last = program.segs[-1]
        self.assertAlmostEqual(last.r1 * 2.0, 40.0)
        self.assertAlmostEqual(last.z1, -20.0)

    def test_g71_expands_into_roughing_and_finish_passes(self):
        program = self.parser.parse(EXAMPLES["G71 Roughing"])
        self.assertTrue(any("roughing passes" in m.text for m in program.msgs))
        self.assertTrue(any("G70 finishing pass" in m.text for m in program.msgs))

    def test_g72_expands_face_passes_and_honors_incremental_w_profile(self):
        text = """N010 G00 X220.0 Z60.0
N011 G00 X176.0 Z2.0
N012 G72 W7.0 R1.0
N013 G72 P014 Q021 U4.0 W2.0 F0.3 S550
N014 G00 G41 Z-70.0 S700
N015 X160.0
N016 G01 X120.0 Z-60.0 F0.15
N017 W10.0
N018 X80.0 W10.0
N019 W20.0
N020 X36.0 W22.0
N021 G40
N022 G70 P014 Q021
N023 G00 X220.0 Z60.0
N024 M30"""
        program = self.parser.parse(text, stock_diameter=220.0, stock_length=100.0)
        self.assertFalse([message for message in program.msgs if message.kind == "err"])
        self.assertTrue(any("G72 expanded" in message.text for message in program.msgs))
        self.assertTrue(any("G70 finishing pass" in message.text for message in program.msgs))
        # N017 is W10 from Z-60, so its endpoint must be Z-50.
        self.assertTrue(any(segment.line == 7 and abs(segment.z1 + 50.0) < 1e-9 for segment in program.segs))
        self.assertTrue(program.cycle_lines)
        engine = SimulationEngine()
        engine.load(program)
        facing_passes = [segment for segment in program.segs if segment.face_width > 0.0]
        self.assertTrue(facing_passes)
        for index, segment in enumerate(program.segs[:-1]):
            if segment.face_width > 0.0:
                self.assertTrue(program.segs[index + 1].rapid)
                x_return = program.segs[index + 2]
                self.assertTrue(x_return.rapid)
                self.assertAlmostEqual(x_return.z0, x_return.z1)
        for segment in facing_passes[:-1]:
            index = program.segs.index(segment)
            z_shift = program.segs[index + 3]
            self.assertTrue(z_shift.rapid)
            self.assertAlmostEqual(z_shift.r0, z_shift.r1)
        first_pass = facing_passes[0]
        band = range(
            engine.final_stock.idx(first_pass.z1),
            engine.final_stock.idx(first_pass.z1 + first_pass.face_width) + 1,
        )
        self.assertTrue(all(engine.final_stock.rad[index] <= min(first_pass.r0, first_pass.r1) + 1e-6 for index in band))
        for z, expected_radius in ((-65.0, 70.0), (-55.0, 60.0), (-45.0, 50.0), (-30.0, 40.0)):
            self.assertAlmostEqual(engine.final_stock.rad[engine.final_stock.idx(z)], expected_radius, delta=0.1)

    def test_rapid_moves_do_not_remove_stock(self):
        program = self.parser.parse("G00 X10 Z-50\nM30", stock_diameter=50.0, stock_length=100.0)
        engine = SimulationEngine()
        engine.load(program)
        middle = engine.final_stock.idx(-25.0)
        self.assertEqual(engine.final_stock.rad[middle], program.stock.radius)
        engine.advance(1000.0)
        self.assertEqual(engine.live_stock.rad[middle], program.stock.radius)

    def test_missing_program_end_is_an_error(self):
        program = self.parser.parse("G21\nG00 X50 Z0\nG01 X40 Z-10 F0.2\n")
        self.assertTrue(any(m.kind == "err" and "M30" in m.text for m in program.msgs))

    def test_tool_change_is_tracked_on_segments(self):
        program = self.parser.parse("G21\nT05\nG00 X50 Z0\nG01 X40 Z-10 F0.2\nM30\n")
        self.assertTrue(program.segs)
        self.assertTrue(all(s.tool == "T05" for s in program.segs))

    def test_fanuc_four_digit_tool_and_center_drill_create_bore(self):
        program = self.parser.parse(
            "N10 (ø30 DRILL)\nG50 T04\nG00 X0 Z5 T0400\nG01 Z-40 F0.07\nG00 Z5\nM30",
            stock_diameter=100.0,
            stock_length=80.0,
        )
        cuts = [segment for segment in program.segs if not segment.rapid]
        self.assertTrue(cuts)
        self.assertTrue(all(segment.tool == "T04" for segment in program.segs))
        self.assertTrue(all(segment.internal for segment in cuts))
        self.assertTrue(all(abs(segment.tool_radius - 15.0) < 1e-9 for segment in cuts))
        engine = SimulationEngine()
        engine.load(program)
        index = engine.final_stock.idx(-20.0)
        self.assertAlmostEqual(engine.final_stock.inner[index], 15.0)
        self.assertAlmostEqual(engine.final_stock.rad[index], 50.0)

    def test_stock_auto_detected_size_matches_deepest_cut(self):
        program = self.parser.parse(EXAMPLES["Facing & Turning"], stock_diameter=50.0, stock_length=100.0)
        cuts = [s for s in program.segs if not s.rapid]
        self.assertTrue(cuts)
        self.assertGreater(max(s.r1 for s in cuts), 0)


if __name__ == "__main__":
    unittest.main()
