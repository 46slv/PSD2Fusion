import tempfile
import unittest
from pathlib import Path

from psd2fusion.fusion_comp import compile_comp
from psd2fusion.semantic import ClippingChain, SemanticDocument, SemanticLayer
from scripts.parity.p4_02 import BASE_ID, MEMBER_IDS, build
from scripts.validate_clipping_subtrees import parse_tools


class P402GraphRecipeTests(unittest.TestCase):
    def test_three_member_fixture_passes_shared_matte_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            report = build(Path(directory))

        self.assertTrue(report["pass"])
        self.assertEqual("PASS", report["status"])
        self.assertEqual("operator_in_fixed_matte_local_stack", report["recipe"])
        self.assertEqual("3", report["graph"]["clipping_count"])
        self.assertTrue(report["checks"]["all_members_reuse_exact_base_matte"])
        self.assertTrue(report["checks"]["one_outer_merge_after_complete_stack"])

    def test_each_member_has_own_in_and_only_the_stack_is_progressive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = build(root)
            tools = parse_tools(root / "p4_02.comp")

        rows = report["members"]
        base_loader = rows[0]["clip_background"]
        self.assertEqual(3, len(rows))
        self.assertEqual(1, len({row["clip_background"] for row in rows}))
        self.assertEqual(base_loader, rows[1]["clip_background"])
        self.assertEqual(base_loader, rows[2]["clip_background"])
        self.assertEqual(rows[0]["stack"], rows[1]["stack_background"])
        self.assertEqual(rows[1]["stack"], rows[2]["stack_background"])
        self.assertNotEqual(rows[0]["stack"], rows[1]["clip_background"])
        self.assertNotEqual(rows[1]["stack"], rows[2]["clip_background"])

        clip_tools = [
            tool
            for tool in tools
            if tool["type"] == "Merge" and tool["operator"] == 'FuID { "In" }'
        ]
        self.assertEqual(3, len(clip_tools))
        self.assertEqual(
            {row["clip"] for row in rows}, {tool["name"] for tool in clip_tools}
        )
        self.assertTrue(all(row["stack_process_alpha"] == "0" for row in rows))

    def test_outer_merge_is_after_all_members_and_local_chain_has_no_outer_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = build(root)
            tools = parse_tools(root / "p4_02.comp")

        outer = report["outer"]
        self.assertIsNotNone(outer)
        self.assertEqual(report["members"][-1]["stack"], outer["foreground"])
        self.assertGreater(
            outer["start"], max(row["stack_start"] for row in report["members"])
        )
        local_names = {
            name
            for row in report["members"]
            for name in (row["clip"], row["stack"])
        }
        outer_sources = {outer["background"], outer["foreground"]}
        for tool in tools:
            if tool["name"] not in local_names:
                continue
            self.assertNotIn(tool["background"], outer_sources)
            self.assertNotIn(tool["foreground"], outer_sources)


class P402MalformedChainTests(unittest.TestCase):
    def test_true_chain_does_not_silently_drop_a_noncontiguous_member(self):
        base = SemanticLayer(
            id=BASE_ID,
            name="base",
            asset_path="assets/base.png",
            clipping_members=list(MEMBER_IDS[:2]),
        )
        first = SemanticLayer(
            id=MEMBER_IDS[0],
            name="first",
            asset_path="assets/first.png",
            clipping_base_id=BASE_ID,
        )
        unrelated = SemanticLayer(
            id="p402otherxx",
            name="unrelated",
            asset_path="assets/other.png",
        )
        second = SemanticLayer(
            id=MEMBER_IDS[1],
            name="second",
            asset_path="assets/second.png",
            clipping_base_id=BASE_ID,
        )
        document = SemanticDocument(
            source_path="malformed-p4-02.psd",
            source_sha256="e" * 64,
            parser="fixture",
            parser_version="1",
            width=4,
            height=4,
            children=[base, first, unrelated, second],
            clipping_chains=[
                ClippingChain(
                    base_id=BASE_ID,
                    member_ids=list(MEMBER_IDS[:2]),
                    blend_clipped_as_group=True,
                )
            ],
        )

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "contiguous same-parent span"):
                compile_comp(document, str(Path(directory) / "malformed.comp"))


if __name__ == "__main__":
    unittest.main()
