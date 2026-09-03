import tempfile
import unittest
from pathlib import Path

from psd2fusion.fusion_comp import FUSION_BLEND_IDS
from scripts.parity.p4_03 import MEMBER_CONTROLS, build
from scripts.validate_clipping_subtrees import parse_tools


class P403MemberControlTests(unittest.TestCase):
    def test_supported_member_modes_and_opacities_stay_on_local_stack(self):
        with tempfile.TemporaryDirectory() as directory:
            report = build(Path(directory))

        self.assertTrue(report["pass"])
        self.assertEqual("PASS", report["status"])
        self.assertEqual("operator_in_fixed_matte_local_stack", report["recipe"])
        self.assertEqual(len(MEMBER_CONTROLS), len(report["members"]))
        self.assertTrue(report["checks"]["each_member_controls_on_local_stack"])
        for row, (mode, opacity) in zip(report["members"], MEMBER_CONTROLS):
            self.assertEqual('FuID { "%s" }' % FUSION_BLEND_IDS[mode], row["blend_function_apply_mode"])
            self.assertEqual("1.000000", row["blend_function_blend"])
            self.assertEqual('FuID { "Normal" }', row["clip_apply_mode"])
            self.assertEqual("1.000000", row["clip_blend"])
            self.assertEqual('FuID { "In" }', row["clip_operator"])
            self.assertEqual('FuID { "Normal" }', row["stack_apply_mode"])
            self.assertEqual("%.6f" % opacity, row["stack_blend"])
            self.assertEqual("0", row["stack_process_alpha"])

    def test_member_controls_do_not_move_to_the_outer_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = build(root)
            tools = parse_tools(root / "p4_03.comp")

        outer = report["outer"]
        self.assertIsNotNone(outer)
        self.assertTrue(report["checks"]["member_modes_are_not_outer_controls"])
        self.assertEqual('FuID { "Normal" }', outer["apply_mode"])
        self.assertEqual("1.000000", outer["blend"])
        stacks = [tool for tool in tools if "P4-03 member opacity local" in tool["comments"]]
        self.assertEqual(len(MEMBER_CONTROLS), len(stacks))
        self.assertEqual(1, len([tool for tool in tools if "PSD clipping chain merge:" in tool["comments"]]))


if __name__ == "__main__":
    unittest.main()
