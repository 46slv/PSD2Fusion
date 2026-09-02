import tempfile
import unittest
from pathlib import Path

from scripts.parity.p4_06 import build


class P406FlowLayoutTests(unittest.TestCase):
    def test_clipping_flow_uses_stable_readable_rows_and_exits_once(self):
        with tempfile.TemporaryDirectory() as directory:
            report = build(Path(directory))

        self.assertTrue(report["pass"])
        self.assertEqual("PASS", report["status"])
        self.assertEqual("operator_in_fixed_matte_local_stack", report["recipe"])
        for name in (
            "flow_is_left_to_right",
            "base_is_below_member_loader_band",
            "member_loaders_have_distinct_rows",
            "clipin_and_stack_are_clustered",
            "fixed_matte_connection_remains_obvious",
            "one_outer_merge_exits_cluster",
        ):
            self.assertTrue(report["checks"][name], name)

    def test_group_operator_positions_are_distinct_from_nested_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            report = build(Path(directory))

        self.assertTrue(report["checks"]["group_boundaries_remain_distinct"])
        groups = report["layout"]["group_boundaries"]
        self.assertEqual(2, len(groups))
        self.assertEqual(2, len(report["layout"]["groups_containing_nested_chain"]))
        self.assertNotEqual(groups[0]["position"], groups[1]["position"])


if __name__ == "__main__":
    unittest.main()
