import tempfile
import unittest
from pathlib import Path

from scripts.parity.p4_01 import compare_candidates
from scripts.validate_clipping_subtrees import parse_tools


class P401GraphRecipeTests(unittest.TestCase):
    def test_candidate_a_is_selected_and_candidate_b_has_alpha_witness(self):
        with tempfile.TemporaryDirectory() as directory:
            report = compare_candidates(Path(directory))

        self.assertTrue(report["pass"])
        self.assertEqual("A", report["selected"])
        self.assertEqual("operator_in_fixed_matte_local_stack", report["recipe"])
        witness = report["witness"]
        self.assertEqual(0.5, witness["candidate_a_local_alpha"])
        self.assertEqual(0.75, witness["candidate_b_ideal_effect_mask_alpha"])
        self.assertTrue(witness["candidate_b_alpha_expands"])
        self.assertTrue(witness["candidate_b_transparent_rgb_requires_explicit_alpha"])

    def test_candidate_a_has_one_local_and_one_outer_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            compare_candidates(root)
            tools = parse_tools(root / "candidate_a.comp")

        loaders = {tool["name"] for tool in tools if tool["type"] == "Loader"}
        self.assertEqual(3, len(loaders))
        clips = [tool for tool in tools if tool["operator"] == 'FuID { "In" }']
        self.assertEqual(1, len(clips))
        clip = clips[0]
        self.assertEqual("LoaderR_p401base00", clip["background"])
        self.assertEqual("LoaderR_p401member", clip["foreground"])
        self.assertIn("P4-01 fixed matte via Operator=In", clip["comments"])

        rgb_nodes = [tool for tool in tools if tool["type"] == "ChannelBoolean"]
        self.assertEqual(1, len(rgb_nodes))
        rgb = rgb_nodes[0]
        self.assertEqual(clip["name"], rgb["background"])
        self.assertEqual("LoaderR_p401member", rgb["foreground"])
        self.assertIn("P4-HOST-PIXEL: ClipIn RGB + member alpha", rgb["comments"])

        stacks = [tool for tool in tools if "P4-01 local Merge" in tool["comments"]]
        self.assertEqual(1, len(stacks))
        stack = stacks[0]
        self.assertEqual(clip["background"], stack["background"])
        self.assertEqual(rgb["name"], stack["foreground"])
        self.assertEqual("0", stack["process_alpha"])

        outers = [tool for tool in tools if "PSD clipping chain merge:" in tool["comments"]]
        self.assertEqual(1, len(outers))
        outer = outers[0]
        self.assertEqual(stack["name"], outer["foreground"])
        self.assertIn("P4-01 outer boundary", outer["comments"])
        self.assertNotEqual(outer["background"], stack["background"])

    def test_candidate_b_is_only_the_direct_effect_mask_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            compare_candidates(root)
            text = (root / "candidate_b.comp").read_text(encoding="utf-8")

        self.assertIn('EffectMask = Input { SourceOp = "LoaderP401_base"', text)
        self.assertNotIn('Operator = Input { Value = FuID { "In" }, }', text)
        self.assertEqual(1, text.count("MergeP401_direct_mask = Merge"))


if __name__ == "__main__":
    unittest.main()
