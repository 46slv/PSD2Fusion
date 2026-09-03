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

    def test_direct_case_stays_on_the_parent_stream_without_group_proxies(self):
        with tempfile.TemporaryDirectory() as directory:
            report = build(Path(directory))

        case = report["cases"]["direct"]
        self.assertEqual([], case["groups"])
        self.assertEqual([], case["containing_groups"])
        self.assertTrue(case["checks"]["direct_chain_stays_in_parent_stream"])

    def test_pass_through_exposes_the_single_outer_merge_as_group_input(self):
        with tempfile.TemporaryDirectory() as directory:
            report = build(Path(directory))

        case = report["cases"]["pass_through"]
        self.assertEqual(1, len(case["groups"]))
        self.assertEqual(1, len(case["containing_groups"]))
        self.assertEqual(
            case["chain"]["outer"]["name"], case["groups"][0]["input_target"]
        )
        self.assertEqual(
            case["chain"]["outer"]["name"],
            case["groups"][0]["proxy"]["input"]["source_op"],
        )
        self.assertEqual("MergeR_p405ptout", case["chain"]["outer"]["background"])
        self.assertTrue(case["checks"]["pass_through_uses_actual_parent_backdrop"])

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

    def test_group_ports_are_proxies_and_render_inputs_use_internal_terminals(self):
        with tempfile.TemporaryDirectory() as directory:
            report = build(Path(directory))

        self.assertTrue(report["checks"]["all_cases_keep_group_proxy_render_split"])
        for case_name in CASES:
            case = report["cases"][case_name]
            for group in case["groups"]:
                self.assertEqual(
                    group["proxy"]["output"], group["render_source"], case_name
                )
                self.assertNotEqual(
                    group["name"], group["render_source"]["source_op"], case_name
                )
                self.assertFalse(group["group_proxy_consumers"], case_name)
                self.assertTrue(group["render_consumers"], case_name)
                if case_name != "pass_through":
                    self.assertIsNone(group["proxy"]["input"], case_name)
                    self.assertEqual(
                        group["render_source"]["source_op"],
                        group["parent_merge"]["foreground"],
                        case_name,
                    )
                else:
                    self.assertIsNotNone(group["proxy"]["input"], case_name)
                    self.assertEqual(
                        group["input_target"],
                        group["proxy"]["input"]["source_op"],
                        case_name,
                    )
                    self.assertEqual(
                        "Background", group["proxy"]["input"]["source"], case_name
                    )

    def test_ordinary_render_inputs_never_reference_group_operator_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            report = build(Path(directory))

        for case_name in CASES:
            case = report["cases"][case_name]
            self.assertTrue(
                case["checks"]["ordinary_render_inputs_avoid_group_proxy"],
                case_name,
            )
            group_names = {group["name"] for group in case["groups"]}
            for group in case["groups"]:
                self.assertNotEqual(
                    group["name"], group["render_source"]["source_op"], case_name
                )
                for consumer in group["render_consumers"]:
                    self.assertNotIn(consumer["source"], group_names, case_name)


if __name__ == "__main__":
    unittest.main()
