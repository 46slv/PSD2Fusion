import tempfile
import unittest
from pathlib import Path

from psd2fusion.capabilities import capability_for_blend, proof_fields_complete
from psd2fusion.compositing import (
    ColorSpaceSpec,
    CompositingError,
    apply_opacity,
    composite_clipping_span_u8,
    composite_isolated_group,
    composite_pass_through_group,
    composite_pixel,
    composite_pixel_u8,
    premultiply,
    unpremultiply,
)
from psd2fusion.fusion_comp import compile_comp
from psd2fusion.semantic import SemanticDocument, SemanticLayer
from scripts.parity.parity003 import generate, validate


class CoreCompositingTests(unittest.TestCase):
    def test_opaque_core_modes(self):
        backdrop = (0.2, 0.5, 0.8, 1.0)
        source = (0.6, 0.4, 0.25, 1.0)
        self.assertEqual((0.6, 0.4, 0.25, 1.0), composite_pixel(backdrop, source, "Normal"))
        self.assertEqual((0.12, 0.2, 0.2, 1.0), composite_pixel(backdrop, source, "Multiply"))
        got = composite_pixel(backdrop, source, "Screen")
        for expected, actual in zip((0.68, 0.7, 0.85, 1.0), got):
            self.assertAlmostEqual(expected, actual)
        self.assertEqual((0.8, 0.9, 1.0, 1.0), composite_pixel(backdrop, source, "Linear Dodge"))
        got = composite_pixel(backdrop, source, "Overlay")
        for expected, actual in zip((0.24, 0.4, 0.7, 1.0), got):
            self.assertAlmostEqual(expected, actual)

    def test_partial_backdrop_alpha_and_source_alpha(self):
        backdrop = (0.2, 0.4, 0.6, 0.5)
        source = (0.8, 0.2, 0.1, 0.5)
        got = composite_pixel(backdrop, source, "Multiply", 0.5)
        self.assertAlmostEqual(0.625, got[3])
        # At zero source alpha, hidden source RGB cannot change the backdrop.
        transparent_source = (0.95, 0.05, 0.9, 0.0)
        self.assertEqual(backdrop, composite_pixel(backdrop, transparent_source, "Overlay", 1.0))
        self.assertEqual(backdrop, apply_opacity(backdrop, 1.0))
        self.assertEqual(backdrop, composite_pixel(backdrop, source, "Normal", 0.0))

    def test_transparent_backdrop_rgb_is_canonical_and_source_remains_visible(self):
        backdrop = (0.8, 0.3, 0.1, 0.0)
        source = (0.2, 0.7, 0.4, 1.0)
        for mode in ("Normal", "Multiply", "Screen", "Linear Dodge", "Overlay"):
            self.assertEqual(source, composite_pixel(backdrop, source, mode))
        self.assertEqual((0.0, 0.0, 0.0, 0.0), composite_pixel(backdrop, source, "Normal", 0.0))

    def test_linear_color_space_is_explicit(self):
        encoded = composite_pixel(
            (0.2, 0.5, 0.8, 1.0),
            (0.6, 0.4, 0.25, 1.0),
            "Overlay",
            color_space="sRGB",
        )
        linear = composite_pixel(
            (0.2, 0.5, 0.8, 1.0),
            (0.6, 0.4, 0.25, 1.0),
            "Overlay",
            color_space=ColorSpaceSpec("linear-sRGB"),
        )
        self.assertNotEqual(encoded, linear)
        self.assertEqual("linear", ColorSpaceSpec("linear-sRGB").transfer)
        with self.assertRaises(CompositingError):
            ColorSpaceSpec("linear-sRGB", transfer="srgb")

    def test_clamp_and_premultiplied_edge(self):
        clamped = composite_pixel((0.9, 0.8, 0.1, 1.0), (0.8, 0.7, 0.9, 1.0), "Linear Dodge")
        unclamped = composite_pixel(
            (0.9, 0.8, 0.1, 1.0), (0.8, 0.7, 0.9, 1.0), "Linear Dodge", clamp=False
        )
        for expected, actual in zip((1.0, 1.0, 1.0, 1.0), clamped):
            self.assertAlmostEqual(expected, actual)
        self.assertGreater(unclamped[0], 1.0)
        edge = (0.8, 0.1, 0.2, 0.375)
        for expected, actual in zip(edge, unpremultiply(premultiply(edge))):
            self.assertAlmostEqual(expected, actual)
        self.assertEqual((0.0, 0.0, 0.0, 0.0), unpremultiply((0.4, 0.1, 0.2, 0.0)))

    def test_isolated_and_nested_group_boundaries(self):
        outer_a = (0.1, 0.2, 0.3, 1.0)
        outer_b = (0.9, 0.8, 0.7, 1.0)
        layers = [((0.8, 0.1, 0.2, 0.75), "Normal", 1.0)]
        isolated_a = composite_isolated_group(outer_a, layers, 0.5)
        isolated_b = composite_isolated_group(outer_b, layers, 0.5)
        self.assertNotEqual(isolated_a, isolated_b)
        inner = composite_isolated_group((0, 0, 0, 0), layers, 0.5)
        nested_outer = (0.1, 0.2, 0.3, 0.5)
        nested = composite_isolated_group(nested_outer, [(inner, "Normal", 1.0)], 0.25)
        self.assertAlmostEqual(0.546875, nested[3])
        self.assertGreater(nested[3], outer_a[3] * 0.25)
        with self.assertRaises(CompositingError):
            composite_pass_through_group(outer_a, layers, 0.5)

    def test_strict_uint8_rounding_matches_fixture_oracle_boundaries(self):
        ordinary = composite_pixel_u8(
            (20, 40, 80, 128), (170, 150, 130, 192), "Normal"
        )
        ordinary = composite_pixel_u8(
            ordinary, (120, 200, 60, 160), "Multiply"
        )
        self.assertEqual((101, 123, 64, 243), ordinary)

        clipped = composite_clipping_span_u8(
            (0, 0, 0, 0),
            (90, 140, 210, 160),
            [
                ((210, 80, 40, 192), "Multiply", 128 / 255.0),
                ((30, 180, 110, 128), "Screen", 192 / 255.0),
            ],
        )
        self.assertEqual((92, 144, 161, 160), clipped)


class CapabilityAndFixtureTests(unittest.TestCase):
    def test_core_registry_remains_unverified_without_host_packet(self):
        for mode in ("Normal", "Multiply", "Screen", "Linear Dodge", "Overlay"):
            record = capability_for_blend(mode)
            self.assertEqual("unverified", record.status)
            self.assertFalse(proof_fields_complete({"candidate_commit": "x", "proof_id": "p", "photoshop": {"version": "not_run"}, "resolve_fusion": {"version": "not_run"}, "metrics": {}}))

    def test_fusion_proof_does_not_require_photoshop(self):
        evidence = {
            "candidate_commit": "x",
            "proof_id": "p",
            "deterministic_fixtures": {"status": "PASS"},
            "psd_provenance": {"status": "PASS", "source_sha256": "b" * 64},
            "resolve_fusion": {
                "version": "21.0.3.7",
                "render_artifact": {"path": "render.png", "sha256": "a" * 64},
            },
            "reference_comparison": {"status": "PASS"},
            "metrics": {"rgba_error": {"max": 0}, "alpha_error": {"max": 0}},
        }
        self.assertTrue(proof_fields_complete(evidence))
        evidence["photoshop"] = {"version": "not_run"}
        self.assertTrue(proof_fields_complete(evidence))

    def test_matrix_generation_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            generated = generate(directory)
            self.assertEqual("PASS", generated["status"])
            result = validate(directory)
            self.assertEqual("PASS", result["status"])
            self.assertEqual(2478, result["blend_cases"])
            self.assertEqual(5, result["recomputed_opacity_cases"])
            self.assertEqual(6, result["recomputed_group_cases"])
            self.assertEqual(0.0, result["max_boundary_error"])
            self.assertEqual("blocked", result["promotion"]["status"])

    def test_unknown_blend_never_falls_back_to_normal(self):
        layer = SemanticLayer("unknown", "Unknown", asset_path="asset.png", blend="Vivid Unknown", raw_blend="zzzz")
        doc = SemanticDocument("fixture.psd", "x" * 64, "fixture", "1", 1, 1, children=[layer])
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                compile_comp(doc, str(Path(directory) / "fixture.comp"))


if __name__ == "__main__":
    unittest.main()
