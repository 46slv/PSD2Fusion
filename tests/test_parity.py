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
        shifted = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        shifted.paste((20, 40, 60, 255), (1, 0, 4, 4))
        ref = Image.new("RGBA", (4, 4), (0, 0, 0, 0)); ref.paste((20, 40, 60, 255), (0, 0, 3, 4))
        p = self.root / "shift.png"; shifted.save(p)
        self.assertEqual("FAIL", compare_images(p, ref)["status"])

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

    def test_wrong_crop_scale_fails(self):
        src = Image.new("RGBA", (8, 8), (20, 40, 60, 255)); src.putpixel((0, 0), (255, 0, 0, 255))
        ref = self.root / "crop-ref.png"; src.save(ref)
        candidate = src.crop((1, 1, 7, 7)).resize((8, 8)); p = self.root / "crop.png"; candidate.save(p)
        self.assertEqual("FAIL", compare_images(p, ref)["status"])

    def test_threshold_validation_and_profile_mismatch(self):
        self.assertEqual("invalid_threshold", compare_images(self.ref, self.ref, threshold=999)["hard_failure"])
        a = Image.new("RGBA", (4, 4), (20, 40, 60, 255)); b = a.copy()
        a.info["icc_profile"], b.info["icc_profile"] = b"profile-a", b"profile-b"
        self.assertEqual("profile_mismatch", compare_images(a, b)["hard_failure"])

    def test_premultiply_fringe_and_signed_artifact(self):
        ref = Image.new("RGBA", (2, 1), (0, 0, 0, 0)); ref.putpixel((0, 0), (200, 0, 0, 128))
        candidate = ref.copy(); candidate.putpixel((0, 0), (100, 0, 0, 128))
        out = self.root / "diff"; got = compare_images(candidate, ref, out)
        self.assertEqual("FAIL", got["status"]); self.assertGreater(got["regions"]["edge_band"]["max"], 0)
        with Image.open(out / "diff_signed.png") as signed:
            self.assertNotEqual(signed.getpixel((0, 0))[0], 128)

    def test_exact_no_profile_is_unverified(self):
        self.assertEqual("UNVERIFIED", compare_images(self.ref, self.ref)["status"])


if __name__ == "__main__":
    unittest.main()
