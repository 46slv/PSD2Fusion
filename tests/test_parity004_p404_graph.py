import tempfile
import unittest
from pathlib import Path

from scripts.parity.p4_04 import MEMBER_CONTROLS, build
from scripts.validate_clipping_subtrees import parse_tools


class P404BaseBoundaryTests(unittest.TestCase):
    def test_base_controls_are_applied_once_at_outer_chain_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            report = build(Path(directory))

        self.assertTrue(report["pass"])
        self.assertEqual("PASS", report["status"])
        self.assertEqual("operator_in_fixed_matte_local_stack", report["recipe"])
        self.assertEqual(('FuID { "Multiply" }', "0.500000"), (
            report["primary_outer"]["apply_mode"], report["primary_outer"]["blend"]
        ))
        self.assertTrue(report["checks"]["outer_boundary_is_after_complete_local_stack"])
        self.assertIn("P4-04 base blend/opacity once", report["primary_outer"]["comments"])

    def test_changing_base_does_not_rewrite_member_local_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = build(root)
            tools = parse_tools(root / "p4_04.comp")

        self.assertTrue(report["checks"]["local_member_controls_do_not_change_with_base"])
        self.assertEqual(report["primary_local_controls"], report["alternate_local_controls"])
        self.assertEqual(2, len([tool for tool in tools if "P4-03 member blend/opacity local" in tool["comments"]]))
        self.assertEqual(1, len([tool for tool in tools if "PSD clipping chain merge:" in tool["comments"]]))
        self.assertEqual(2, len(MEMBER_CONTROLS))


if __name__ == "__main__":
    unittest.main()
