import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from scripts.parity.parity import compare_images


class ComparatorFalsePassTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ref = self.root / "ref.png"
        Image.new("RGBA", (4, 4), (20, 40, 60, 255)).save(self.ref)

    def tearDown(self):
        self.tmp.cleanup()

    def test_one_pixel_translation_is_not_pass(self):
        shifted = Image.new("RGBA", (4, 4), (20, 40, 60, 255)); shifted.putpixel((0, 0), (0, 0, 0, 255))
        p = self.root / "shift.png"; shifted.save(p)
        self.assertEqual("FAIL", compare_images(p, self.ref)["status"])

    def test_dimension_mismatch_is_hard_failure(self):
        p = self.root / "wrong.png"; Image.new("RGBA", (5, 4)).save(p)
        got = compare_images(p, self.ref)
        self.assertEqual("dimension_mismatch", got["hard_failure"])

    def test_rgb_match_wrong_alpha_fails(self):
        p = self.root / "alpha.png"; Image.new("RGBA", (4, 4), (20, 40, 60, 0)).save(p)
        got = compare_images(p, self.ref)
        self.assertEqual("FAIL", got["status"]); self.assertGreater(got["alpha_error"]["max"], 0)

    def test_threshold_cannot_hide_large_outlier(self):
        p = self.root / "outlier.png"; im = Image.new("RGBA", (20, 20), (20, 40, 60, 255)); im.putpixel((10, 10), (255, 255, 255, 255)); im.save(p)
        ref = self.root / "outlier-ref.png"; Image.new("RGBA", (20, 20), (20, 40, 60, 255)).save(ref)
        got = compare_images(p, ref)
        self.assertGreater(got["threshold_exceeding"]["count"], 0)


if __name__ == "__main__":
    unittest.main()
