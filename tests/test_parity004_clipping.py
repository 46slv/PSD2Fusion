import json
import tempfile
import unittest
from pathlib import Path

from psd2fusion.compositing import composite_clipping_span
from scripts.parity.parity004 import generate, validate


class ClippingOracleTests(unittest.TestCase):
    def test_fixed_base_coverage_and_member_order(self):
        base = (0.2, 0.4, 0.8, 0.5)
        members = [
            ((1.0, 0.0, 0.0, 1.0), "Normal", 1.0),
            ((0.0, 1.0, 0.0, 0.5), "Multiply", 0.5),
        ]
        result = composite_clipping_span((0.0, 0.0, 0.0, 0.0), base, members)
        self.assertAlmostEqual(0.5, result[3])
        reversed_result = composite_clipping_span(
            (0.0, 0.0, 0.0, 0.0), base, list(reversed(members))
        )
        self.assertNotEqual(result[:3], reversed_result[:3])

    def test_zero_matte_and_zero_opacity_members_are_noops(self):
        base = (0.8, 0.1, 0.2, 0.0)
        member = ((1.0, 1.0, 1.0, 1.0), "Linear Dodge", 1.0)
        result = composite_clipping_span((0.1, 0.2, 0.3, 1.0), base, [member])
        self.assertEqual((0.1, 0.2, 0.3, 1.0), result)
        opaque = composite_clipping_span(
            (0.0, 0.0, 0.0, 1.0),
            (0.2, 0.3, 0.4, 1.0),
            [((1.0, 0.0, 0.0, 1.0), "Overlay", 0.0)],
        )
        self.assertEqual((0.2, 0.3, 0.4, 1.0), opaque)

    def test_base_opacity_is_applied_once_at_outer_boundary(self):
        base = (1.0, 0.0, 0.0, 0.75)
        member = ((0.0, 1.0, 0.0, 1.0), "Normal", 1.0)
        result = composite_clipping_span(
            (0.0, 0.0, 1.0, 1.0), base, [member], base_opacity=0.5
        )
        # Base coverage stays .75; only the completed span is attenuated.
        self.assertAlmostEqual(1.0, result[3])
        self.assertTrue(all(0.0 <= value <= 1.0 for value in result))

    def test_member_coverage_is_relative_to_fixed_matte(self):
        # A fully opaque Normal member replaces the local color wherever the
        # base matte has coverage; a fractional matte must not amplify it.
        base = (0.2, 0.4, 0.8, 0.25)
        member = ((0.9, 0.1, 0.3, 1.0), "Normal", 1.0)
        result = composite_clipping_span(
            (0.0, 0.0, 0.0, 0.0), base, [member]
        )
        self.assertEqual((0.9, 0.1, 0.3, 0.25), result)

    def test_base_and_member_opacity_are_independent_stages(self):
        base = (0.2, 0.4, 0.8, 0.5)
        member = ((0.9, 0.1, 0.3, 1.0), "Normal", 0.5)
        full_base = composite_clipping_span(
            (0.0, 0.0, 0.0, 0.0), base, [member], base_opacity=1.0
        )
        attenuated_base = composite_clipping_span(
            (0.0, 0.0, 0.0, 0.0), base, [member], base_opacity=0.5
        )
        self.assertAlmostEqual(0.5, full_base[3])
        self.assertAlmostEqual(0.25, attenuated_base[3])
        self.assertEqual(full_base[:3], attenuated_base[:3])

    def test_transparent_rgb_does_not_fringe(self):
        result = composite_clipping_span(
            (0.0, 0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0, 0.0),
            [((0.0, 1.0, 0.0, 0.5), "Multiply", 1.0)],
        )
        self.assertEqual((0.0, 0.0, 0.0, 0.0), result)

    def test_fixture_expected_pixels_are_not_a_circular_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual("PASS", generate(root)["status"])
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["cases"][0]["expected"][0] += 0.125
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = validate(root)
            self.assertEqual("FAIL", result["status"])
            self.assertGreater(result["max_reference_error"], 0.1)


if __name__ == "__main__":
    unittest.main()
