"""Focused structural proof for the Linear Dodge late-clamp island.

A clipped Linear Dodge member attenuates its premultiplied stream to its
opacity in float32 *before* the opaque add, so saturation happens only once
at the clamp; the fixed base coverage M is reattached afterwards and the
completed result replaces the local stream.  Every other mode keeps the
strict island (member opacity on the local ClipStack Merge Blend control).
No quantization, depth change, or L52-specific special case is allowed.
"""

import tempfile
import unittest
from pathlib import Path

from psd2fusion.fusion_comp import FUSION_BLEND_IDS, compile_comp
from psd2fusion.semantic import ClippingChain, SemanticDocument, SemanticLayer
from scripts.validate_clipping_subtrees import parse_tools


BASE_ID = "ldlatebase1"
MEMBER_IDS = ("ldlatenorm01", "ldlatemult01", "ldlatelddg01")


def fixture_document() -> SemanticDocument:
    base = SemanticLayer(
        id=BASE_ID,
        name="LD late-clamp base",
        asset_path="assets/base.png",
        blend="Normal",
        clipping_members=list(MEMBER_IDS),
    )
    members = [
        SemanticLayer(
            id="ldlatenorm01",
            name="LD late-clamp Normal control",
            asset_path="assets/normal.png",
            clipping_base_id=BASE_ID,
            blend="Normal",
            opacity=1.0,
        ),
        SemanticLayer(
            id="ldlatemult01",
            name="LD late-clamp Multiply control",
            asset_path="assets/multiply.png",
            clipping_base_id=BASE_ID,
            blend="Multiply",
            opacity=0.5,
        ),
        SemanticLayer(
            id="ldlatelddg01",
            name="LD late-clamp Linear Dodge member",
            asset_path="assets/linear-dodge.png",
            clipping_base_id=BASE_ID,
            blend="Linear Dodge",
            opacity=0.5,
        ),
    ]
    return SemanticDocument(
        source_path="ld-late-clamp-fixture.psd",
        source_sha256="0" * 64,
        parser="fixture",
        parser_version="1",
        width=8,
        height=8,
        children=[base] + members,
        clipping_chains=[
            ClippingChain(
                base_id=BASE_ID,
                member_ids=list(MEMBER_IDS),
                blend_clipped_as_group=True,
                blend_clipped_as_group_provenance="photoshop_default_true",
            )
        ],
    )


def _role(tools, prefix, member_id):
    suffix = "_" + member_id[:10]
    return [
        tool
        for tool in tools
        if tool["name"].startswith(prefix)
        and (tool["name"].endswith(suffix) or suffix + "_" in tool["name"])
    ]


def _one(tools, prefix, member_id, tool_type):
    found = [t for t in _role(tools, prefix, member_id) if t["type"] == tool_type]
    assert len(found) == 1, (prefix, member_id, len(found))
    return found[0]


class LDLateClampIslandTests(unittest.TestCase):
    def test_linear_dodge_uses_attenuated_late_clamp_wiring(self):
        with tempfile.TemporaryDirectory() as directory:
            comp_path = Path(directory) / "ld-late-clamp.comp"
            compile_comp(fixture_document(), str(comp_path))
            tools = parse_tools(comp_path)

        member_id = "ldlatelddg01"
        loader = _one(tools, "Loader", member_id, "Loader")
        attenuate = _one(tools, "BlendMemberAttenuate", member_id, "BrightnessContrast")
        # Opacity lives in the float32 Gain, applied exactly once.
        self.assertEqual("0.500000", attenuate["gain"])
        self.assertEqual("0", attenuate["process_alpha"])
        self.assertIsNone(attenuate["clip_black"])
        self.assertIsNone(attenuate["clip_white"])
        self.assertEqual(loader["name"], attenuate["input"])
        opaque = _one(tools, "BlendMemberOpaque", member_id, "ChannelBoolean")
        self.assertEqual(attenuate["name"], opaque["background"])
        self.assertEqual("16", opaque["to_alpha"])
        function = _one(tools, "BlendFunction", member_id, "Merge")
        self.assertEqual('FuID { "%s" }' % FUSION_BLEND_IDS["Linear Dodge"], function["apply_mode"])
        self.assertEqual("1.000000", function["blend"])
        coverage = _one(tools, "BlendCoverage", member_id, "ChannelBoolean")
        base_loader = _one(tools, "Loader", BASE_ID, "Loader")
        # Fixed base coverage M is attached, never the M*A intersection.
        self.assertEqual(base_loader["name"], coverage["foreground"])
        self.assertEqual("3", coverage["to_alpha"])
        restore = _one(tools, "BlendRestoreAlpha", member_id, "ChannelBoolean")
        self.assertEqual("16", restore["to_alpha"])
        self.assertIsNone(restore["foreground"])
        stack = _one(tools, "ClipStack", member_id, "Merge")
        self.assertEqual('FuID { "Normal" }', stack["apply_mode"])
        self.assertEqual("1.000000", stack["blend"])
        self.assertEqual("0", stack["process_alpha"])
        # The fixed matte is still emitted as structural evidence.
        clips = [t for t in _role(tools, "ClipIn", member_id) if t["type"] == "Merge"]
        self.assertEqual(1, len(clips))
        self.assertEqual('FuID { "In" }', clips[0]["operator"])

    def test_other_modes_keep_strict_wiring_without_attenuate(self):
        with tempfile.TemporaryDirectory() as directory:
            comp_path = Path(directory) / "ld-late-clamp.comp"
            compile_comp(fixture_document(), str(comp_path))
            tools = parse_tools(comp_path)

        for member_id, opacity in (("ldlatenorm01", "1.000000"), ("ldlatemult01", "0.500000")):
            self.assertEqual(
                [], _role(tools, "BlendMemberAttenuate", member_id),
                member_id,
            )
            stack = _one(tools, "ClipStack", member_id, "Merge")
            self.assertEqual(opacity, stack["blend"])
            self.assertEqual("0", stack["process_alpha"])
            restore = _one(tools, "BlendRestoreAlpha", member_id, "ChannelBoolean")
            self.assertEqual("3", restore["to_alpha"])
            self.assertIsNotNone(restore["foreground"])

    def test_no_id_specific_special_case(self):
        with tempfile.TemporaryDirectory() as directory:
            comp_path = Path(directory) / "ld-late-clamp.comp"
            compile_comp(fixture_document(), str(comp_path))
            text = comp_path.read_text(encoding="utf-8")
        self.assertNotIn("febb790170", text)
        self.assertNotIn("cdf6d2a082", text)


if __name__ == "__main__":
    unittest.main()
