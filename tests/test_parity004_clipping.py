import unittest

from psd2fusion.compositing import composite_clipping_span


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

    def test_transparent_rgb_does_not_fringe(self):
        result = composite_clipping_span(
            (0.0, 0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0, 0.0),
            [((0.0, 1.0, 0.0, 0.5), "Multiply", 1.0)],
        )
        self.assertEqual((0.0, 0.0, 0.0, 0.0), result)


if __name__ == "__main__":
    unittest.main()
