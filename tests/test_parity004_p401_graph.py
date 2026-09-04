import tempfile
import unittest
from pathlib import Path

from scripts.parity.p4_01 import compare_candidates
from scripts.validate_clipping_subtrees import materialization_for, parse_tools


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
        base_source = materialization_for(tools, "p401base00")["source"]
        member_source = materialization_for(tools, "p401member")["source"]
        self.assertEqual("MaterializePremultR_p401base00", base_source)
        self.assertEqual("MaterializePremultR_p401member", member_source)
        self.assertEqual(base_source, clip["background"])
        self.assertEqual(member_source, clip["foreground"])
        self.assertIn("P4-01 fixed matte via Operator=In", clip["comments"])

        base_straight = [tool for tool in tools if tool["name"].startswith("BlendBaseStraight")]
        base_opaque = [tool for tool in tools if tool["name"].startswith("BlendBaseOpaque")]
        member_straight = [tool for tool in tools if tool["name"].startswith("BlendMemberStraight")]
        member_opaque = [tool for tool in tools if tool["name"].startswith("BlendMemberOpaque")]
        functions = [tool for tool in tools if tool["name"].startswith("BlendFunction")]
        clamps = [tool for tool in tools if tool["name"].startswith("BlendClamp")]
        coverages = [tool for tool in tools if tool["name"].startswith("BlendCoverage")]
        premults = [tool for tool in tools if tool["name"].startswith("BlendPremult")]
        restores = [tool for tool in tools if tool["name"].startswith("BlendRestoreAlpha")]
        self.assertEqual(1, len(base_straight))
        self.assertEqual(1, len(base_opaque))
        self.assertEqual(1, len(member_straight))
        self.assertEqual(1, len(member_opaque))
        self.assertEqual(1, len(functions))
        self.assertEqual(1, len(clamps))
        self.assertEqual(1, len(coverages))
        self.assertEqual(1, len(premults))
        self.assertEqual(1, len(restores))
        self.assertEqual(clip["name"], coverages[0]["foreground"])
        self.assertEqual(base_straight[0]["name"], base_opaque[0]["background"])
        self.assertEqual(member_straight[0]["name"], member_opaque[0]["background"])
        self.assertEqual(base_opaque[0]["name"], functions[0]["background"])
        self.assertEqual(member_opaque[0]["name"], functions[0]["foreground"])
        self.assertEqual("1.000000", functions[0]["blend"])
        self.assertEqual(functions[0]["name"], clamps[0]["input"])
        self.assertEqual(clamps[0]["name"], coverages[0]["background"])
        self.assertEqual(coverages[0]["name"], premults[0]["input"])
        self.assertEqual(premults[0]["name"], restores[0]["background"])
        self.assertEqual(member_source, restores[0]["foreground"])
        self.assertEqual("3", restores[0]["to_alpha"])

        stacks = [tool for tool in tools if "P4-01 local Merge" in tool["comments"]]
        self.assertEqual(1, len(stacks))
        stack = stacks[0]
        self.assertEqual(clip["background"], stack["background"])
        self.assertEqual(restores[0]["name"], stack["foreground"])
        self.assertEqual('FuID { "Normal" }', stack["apply_mode"])
        self.assertEqual("1.000000", stack["blend"])
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
