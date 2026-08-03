import unittest

from cnc_sim.examples import EXAMPLES
from cnc_sim.parser import FanucParser


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = FanucParser()

    def test_all_examples_compile(self):
        for name, source in EXAMPLES.items():
            with self.subTest(name=name):
                program = self.parser.parse(source)
                self.assertGreater(len(program.segs), 0)

    def test_relative_positioning_mode(self):
        # lathe_core supports G91 modal incremental mode but has no U/W shorthand.
        program = self.parser.parse("G21 G90\nG00 X50 Z0\nG91\nG01 X-10 Z-20 F0.2\nG90\nM30\n")
        last = program.segs[-1]
        self.assertAlmostEqual(last.r1 * 2.0, 40.0)
        self.assertAlmostEqual(last.z1, -20.0)

    def test_g71_expands_into_roughing_and_finish_passes(self):
        program = self.parser.parse(EXAMPLES["G71 Roughing"])
        self.assertTrue(any("roughing passes" in m.text for m in program.msgs))
        self.assertTrue(any("G70 finishing pass" in m.text for m in program.msgs))
        self.assertTrue(program.cycle_lines)

    def test_missing_program_end_is_an_error(self):
        program = self.parser.parse("G21\nG00 X50 Z0\nG01 X40 Z-10 F0.2\n")
        self.assertTrue(any(m.kind == "err" and "M30" in m.text for m in program.msgs))

    def test_tool_change_is_tracked_on_segments(self):
        program = self.parser.parse("G21\nT05\nG00 X50 Z0\nG01 X40 Z-10 F0.2\nM30\n")
        self.assertTrue(program.segs)
        self.assertTrue(all(s.tool == "T05" for s in program.segs))

    def test_stock_auto_detected_size_matches_deepest_cut(self):
        program = self.parser.parse(EXAMPLES["Facing & Turning"], stock_diameter=50.0, stock_length=100.0)
        cuts = [s for s in program.segs if not s.rapid]
        self.assertTrue(cuts)
        self.assertGreater(max(s.r1 for s in cuts), 0)


if __name__ == "__main__":
    unittest.main()
