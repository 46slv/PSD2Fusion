import tempfile
import unittest
from pathlib import Path

from scripts.parity.p4_05 import CASES, build


class P405GroupBoundaryTests(unittest.TestCase):
    def test_clipping_recipe_survives_group_boundary_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            report = build(Path(directory))

        self.assertTrue(report["pass"])
        self.assertEqual("PASS", report["status"])
        self.assertEqual("operator_in_fixed_matte_local_stack", report["recipe"])
        self.assertEqual(set(CASES), set(report["cases"]))
        for case in CASES:
            self.assertTrue(report["cases"][case]["pass"], case)
            self.assertTrue(
                report["cases"][case]["checks"]["clipping_recipe_inside_existing_stream"],
                case,
            )

    def test_pass_through_exposes_the_single_outer_merge_as_group_input(self):
        with tempfile.TemporaryDirectory() as directory:
            report = build(Path(directory))

        case = report["cases"]["pass_through"]
        self.assertEqual(1, len(case["groups"]))
        self.assertEqual(1, len(case["containing_groups"]))
        self.assertEqual(
            case["chain"]["outer"]["name"], case["groups"][0]["input_target"]
        )

    def test_nested_and_adjacent_cases_keep_distinct_group_ownership(self):
        with tempfile.TemporaryDirectory() as directory:
            report = build(Path(directory))

        nested = report["cases"]["nested_isolated"]
        self.assertEqual(2, len(nested["groups"]))
        self.assertEqual(2, len(nested["containing_groups"]))
        adjacent = report["cases"]["adjacent"]
        self.assertEqual(2, len(adjacent["groups"]))
        self.assertEqual([], adjacent["containing_groups"])
        outer_start = adjacent["chain"]["outer"]["start"]
        self.assertLess(adjacent["groups"][0]["end"], outer_start)
        self.assertLess(outer_start, adjacent["groups"][1]["start"])


if __name__ == "__main__":
    unittest.main()
