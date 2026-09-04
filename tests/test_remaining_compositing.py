import tempfile
import unittest
from pathlib import Path

from psd2fusion.compositing import blend_rgb, composite_pixel
from psd2fusion.fusion_comp import compile_comp
from psd2fusion.semantic import SemanticDocument, SemanticLayer
from scripts.parity.p4_05 import _all_tools, _proxy_contracts


SOURCE_HASH = "f" * 64


def _layer(layer_id, name, *, blend="Normal", opacity=1.0):
    return SemanticLayer(
        id=layer_id,
        name=name,
        asset_path="assets/%s.png" % layer_id,
        raw_blend={
            "Normal": "norm",
            "Multiply": "mul ",
            "Screen": "scrn",
        }.get(blend, "unknown"),
        blend=blend,
        opacity=opacity,
    )


def _document(children):
    return SemanticDocument(
        source_path="remaining-compositing.psd",
        source_sha256=SOURCE_HASH,
        parser="fixture",
        parser_version="1",
        width=4,
        height=4,
        children=list(children),
    )


def _one(tools, prefix, layer_id, tool_type=None):
    suffix = "_" + layer_id[:10]
    matches = [
        tool
        for tool in tools
        if tool["name"].startswith(prefix)
        and (tool["name"].endswith(suffix) or suffix + "_" in tool["name"])
        and (tool_type is None or tool["type"] == tool_type)
    ]
    if len(matches) != 1:
        raise AssertionError(
            "expected one %s/%s for %s, got %r"
            % (prefix, tool_type, layer_id, [tool["name"] for tool in matches])
        )
    return matches[0]


class RemainingCompositingLoweringTests(unittest.TestCase):
    def _compile(self, document, directory, name="fixture.comp"):
        path = Path(directory) / name
        stats = compile_comp(document, str(path))
        return path, stats, _all_tools(path)

    def test_ordinary_multiply_and_screen_use_straight_opaque_function_islands(self):
        for mode in ("Multiply", "Screen"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                backdrop = _layer("ordinarybackdrop", "Backdrop", opacity=0.5)
                source = _layer(
                    "ordinarysource", "Source", blend=mode, opacity=0.625
                )
                path, stats, tools = self._compile(
                    _document([backdrop, source]), directory
                )

                function = _one(
                    tools, "LayerBlendFunctionR", source.id, "Merge"
                )
                backdrop_opaque = _one(
                    tools, "LayerBlendBackdropOpaqueR", source.id, "ChannelBoolean"
                )
                source_opaque = _one(
                    tools, "LayerBlendSourceOpaqueR", source.id, "ChannelBoolean"
                )
                coverage = _one(
                    tools, "LayerBlendCoverageR", source.id, "Merge"
                )
                canvas = _one(
                    tools, "LayerBlendCanvasR", source.id, "Background"
                )
                final = _one(tools, "MergeR", source.id, "Merge")

                self.assertEqual('FuID { "%s" }' % mode, function["apply_mode"])
                self.assertEqual(backdrop_opaque["name"], function["background"])
                self.assertEqual(source_opaque["name"], function["foreground"])
                self.assertEqual("16", backdrop_opaque["to_alpha"])
                self.assertEqual("16", source_opaque["to_alpha"])
                self.assertEqual(canvas["name"], coverage["background"])
                self.assertEqual("0.625000", coverage["blend"])
                self.assertEqual("1", coverage["process_alpha"])
                self.assertEqual('FuID { "Normal" }', final["apply_mode"])
                self.assertEqual("1", final["process_alpha"])
                self.assertNotEqual(function["name"], final["name"])
                self.assertIn(mode, stats["blend_modes"])
                self.assertEqual(
                    2,
                    path.read_text(encoding="utf-8").count(
                        '["Clip1.PNGFormat.PostMultiply"] = Input { Value = 1, }'
                    ),
                )

    def test_straight_boundary_algebra_matches_source_over_oracle(self):
        backdrops = (
            (0.0, 0.0, 0.0, 0.0),
            (0.2, 0.6, 0.9, 0.25),
            (0.9, 0.3, 0.1, 0.625),
            (0.4, 0.5, 0.2, 1.0),
        )
        sources = (
            (0.8, 0.1, 0.4, 0.125),
            (0.3, 0.9, 0.2, 0.5),
            (0.7, 0.4, 0.95, 1.0),
        )
        for mode in ("Multiply", "Screen", "Linear Dodge", "Overlay"):
            for backdrop in backdrops:
                for source in sources:
                    for opacity in (0.0, 0.375, 1.0):
                        with self.subTest(
                            mode=mode,
                            backdrop_alpha=backdrop[3],
                            source_alpha=source[3],
                            opacity=opacity,
                        ):
                            expected = composite_pixel(
                                backdrop, source, mode, opacity
                            )
                            blended = blend_rgb(backdrop[:3], source[:3], mode)
                            straight_mix = tuple(
                                (1.0 - backdrop[3]) * source[channel]
                                + backdrop[3] * blended[channel]
                                for channel in range(3)
                            )
                            coverage = source[3] * opacity
                            output_alpha = coverage + backdrop[3] * (1.0 - coverage)
                            if output_alpha == 0.0:
                                actual = (0.0, 0.0, 0.0, 0.0)
                            else:
                                premultiplied = tuple(
                                    coverage * straight_mix[channel]
                                    + backdrop[3]
                                    * (1.0 - coverage)
                                    * backdrop[channel]
                                    for channel in range(3)
                                )
                                actual = tuple(
                                    value / output_alpha for value in premultiplied
                                ) + (output_alpha,)
                            for left, right in zip(expected, actual):
                                self.assertAlmostEqual(left, right, places=14)

    def test_nested_isolated_screen_never_routes_render_through_group_proxy(self):
        child_backdrop = _layer("nestedchildback", "Child backdrop", opacity=0.75)
        child_screen = _layer(
            "nestedchildscreen", "Child screen", blend="Screen", opacity=0.5
        )
        group = SemanticLayer(
            id="nestedisogroup",
            name="Nested isolated group",
            kind="group",
            children=[child_backdrop, child_screen],
            isolated=True,
            blend="Screen",
            raw_blend="scrn",
            opacity=0.625,
        )
        backdrop = _layer("nestedouterback", "Outer backdrop", opacity=0.5)

        with tempfile.TemporaryDirectory() as directory:
            path, _, tools = self._compile(
                _document([backdrop, group]), directory
            )
            group_tools = [
                tool for tool in tools if tool["type"] == "GroupOperator"
            ]
            self.assertEqual(1, len(group_tools))
            proxy = _proxy_contracts(path, group_tools)[group_tools[0]["name"]]

        self.assertIsNone(proxy["input"])
        self.assertIsNotNone(proxy["output"])
        render_inputs = ("background", "foreground", "input", "effect_mask")
        self.assertFalse(
            any(
                tool.get(input_name) == group_tools[0]["name"]
                for tool in tools
                for input_name in render_inputs
            )
        )

        child_function = _one(
            tools, "LayerBlendFunctionRI", child_screen.id, "Merge"
        )
        group_function = _one(
            tools, "LayerBlendFunctionR", group.id, "Merge"
        )
        self.assertEqual('FuID { "Screen" }', child_function["apply_mode"])
        self.assertEqual('FuID { "Screen" }', group_function["apply_mode"])
        self.assertEqual(
            proxy["output"]["source_op"],
            _one(tools, "LayerBlendSourceStraightR", group.id, "AlphaDivide")[
                "input"
            ],
        )

    def test_pass_through_nonnormal_child_exposes_first_real_input_port(self):
        backdrop = _layer("passthroughback", "Outer backdrop", opacity=0.5)
        child = _layer(
            "passthroughchild", "Pass-through multiply", blend="Multiply", opacity=0.75
        )
        group = SemanticLayer(
            id="passthroughgroup",
            name="Pass Through",
            kind="group",
            children=[child],
            pass_through=True,
            isolated=False,
        )

        with tempfile.TemporaryDirectory() as directory:
            path, _, tools = self._compile(_document([backdrop, group]), directory)
            group_tools = [
                tool for tool in tools if tool["type"] == "GroupOperator"
            ]
            self.assertEqual(1, len(group_tools))
            contract = _proxy_contracts(path, group_tools)[group_tools[0]["name"]]

        first_consumer = _one(
            tools, "LayerBlendBackdropStraightRP", child.id, "AlphaDivide"
        )
        self.assertEqual(
            {"source_op": first_consumer["name"], "source": "Input"},
            contract["input"],
        )
        self.assertEqual('FuID { "Multiply" }', _one(
            tools, "LayerBlendFunctionRP", child.id, "Merge"
        )["apply_mode"])
        self.assertFalse(
            any(
                tool.get(input_name) == group_tools[0]["name"]
                for tool in tools
                for input_name in ("background", "foreground", "input", "effect_mask")
            )
        )

    def test_mapped_but_rejected_mode_cannot_bypass_capability_registry(self):
        document = _document(
            [_layer("rejectedsource", "Rejected", blend="Color Burn")]
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                ValueError, "rejected by the strict capability registry: Color Burn"
            ):
                compile_comp(document, str(Path(directory) / "rejected.comp"))


if __name__ == "__main__":
    unittest.main()
