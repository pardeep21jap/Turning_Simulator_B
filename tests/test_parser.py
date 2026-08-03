import unittest

from cnc_sim.examples import EXAMPLES
from cnc_sim.models import MotionKind
from cnc_sim.parser import FanucParser


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = FanucParser()

    def test_all_examples_generate_motion(self):
        for name, source in EXAMPLES.items():
            with self.subTest(name=name):
                program = self.parser.parse(source)
                self.assertGreater(len(program.motions), 0)
                self.assertFalse([a for a in program.alarms if a.severity == "error"], program.alarms)

    def test_incremental_coordinates(self):
        program = self.parser.parse("G21 G90\nG00 X50 Z0\nG01 U-10 W-20 F0.2\n")
        self.assertEqual(program.motions[-1].end_x, 40)
        self.assertEqual(program.motions[-1].end_z, -20)

    def test_spindle_warning(self):
        program = self.parser.parse("G21\nG00 X50 Z0\nG01 X40 Z-10 F0.2\n")
        self.assertTrue(any(a.code == "SP001" for a in program.alarms))

    def test_thread_cycle(self):
        program = self.parser.parse(EXAMPLES["G76 Threading"])
        self.assertTrue(any(m.kind == MotionKind.THREAD for m in program.motions))

    def test_unknown_g_code_is_error(self):
        program = self.parser.parse("G123 X10 Z-5")
        self.assertTrue(any(a.code == "PS010" and a.severity == "error" for a in program.alarms))

    def test_rapid_into_stock_warns(self):
        program = self.parser.parse("G21\nG00 X60 Z5\nG00 X40 Z-20\n")
        self.assertTrue(any(a.code == "CL001" for a in program.alarms))


if __name__ == "__main__":
    unittest.main()
