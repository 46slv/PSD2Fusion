import tempfile
import unittest
from pathlib import Path

from psd_tools.constants import Tag

from psd2fusion.fusion_comp import compile_comp
from psd2fusion.parse_psd import _blend_clipped_as_group
from psd2fusion.semantic import ClippingChain, SemanticDocument, SemanticLayer


class _TaggedBlocks(dict):
    def get_data(self, key):
        return self[key]


class _RawLayer:
    def __init__(self, value=None):
        self.tagged_blocks = _TaggedBlocks()
        if value is not None:
            self.tagged_blocks[Tag.BLEND_CLIPPING_ELEMENTS] = value


class ClippingSemanticTests(unittest.TestCase):
    def test_clbl_default_and_explicit_provenance_are_distinct(self):
        self.assertEqual(
            (True, "photoshop_default_true"), _blend_clipped_as_group(_RawLayer())
        )
        self.assertEqual(
            (True, "explicit_psd_clbl"), _blend_clipped_as_group(_RawLayer(1))
        )
        self.assertEqual(
            (False, "explicit_psd_clbl"), _blend_clipped_as_group(_RawLayer(0))
        )


class ClippingCompilerTests(unittest.TestCase):
    def test_multiple_members_stay_in_subtree_until_base_scope_merge(self):
        base = SemanticLayer(
            id="base000000000001",
            name="partial alpha base",
            asset_path="assets/base.png",
            blend="Normal",
            clipping_members=["member0000000001", "member0000000002"],
        )
        normal = SemanticLayer(
            id="member0000000001",
            name="normal clip",
            asset_path="assets/normal.png",
            clipping_base_id=base.id,
            blend="Normal",
        )
        multiply = SemanticLayer(
            id="member0000000002",
            name="multiply opacity clip",
            asset_path="assets/multiply.png",
            clipping_base_id=base.id,
            blend="Multiply",
            opacity=0.5,
        )
        doc = SemanticDocument(
            source_path="fixture.psd",
            source_sha256="f" * 64,
            parser="fixture",
            parser_version="1",
            width=4,
            height=4,
            children=[base, normal, multiply],
            clipping_chains=[
                ClippingChain(
                    base_id=base.id,
                    member_ids=[normal.id, multiply.id],
                    blend_clipped_as_group=True,
                    blend_clipped_as_group_provenance="photoshop_default_true",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fixture.comp"
            stats = compile_comp(doc, str(output))
            text = output.read_text(encoding="utf-8")

        self.assertEqual("2", stats["clipping_count"])
        self.assertIn("PSD clipping subtree member", text)
        self.assertEqual(2, text.count("ProcessAlpha = Input { Value = 0, }"))
        self.assertIn('ApplyMode = Input { Value = FuID { "Multiply" }, }', text)
        self.assertIn("Blend = Input { Value = 0.500000, }", text)
        self.assertEqual(1, text.count("PSD clipping chain merge"))
        self.assertNotIn("PSD clipped layer merge", text)

        base_loader = text.index("PSD layer: partial alpha base")
        first_member = text.index("PSD clipping subtree member (base=base000000000001): normal clip")
        second_member = text.index(
            "PSD clipping subtree member (base=base000000000001): multiply opacity clip"
        )
        outer_merge = text.index("PSD clipping chain merge: partial alpha base")
        self.assertLess(base_loader, first_member)
        self.assertLess(first_member, second_member)
        self.assertLess(second_member, outer_merge)

        final_start = text.rfind("\n\t\tMerge", 0, outer_merge)
        final_block = text[final_start : outer_merge + 80]
        self.assertIn('Background = Input { SourceOp = "Background_', final_block)
        self.assertIn('Foreground = Input { SourceOp = "ClipStackR_', final_block)


if __name__ == "__main__":
    unittest.main()
