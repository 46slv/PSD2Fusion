"""PARITY-005 P5-01: byte-backed clbl provenance on the BASE layer.

Stage S0 / Axis A. Parser + bytes only. No Fusion/compositing truth.
Proves three classes survive PSD save->reopen->parse_psd:
  absent -> (True, photoshop_default_true)
  explicit 1 -> (True, explicit_psd_clbl)
  explicit 0 -> (False, explicit_psd_clbl)
Absent and explicit-true MUST NOT be semantically equated (provenance differs).
"""
import hashlib
import os
import tempfile
import unittest

from PIL import Image
from psd_tools import PSDImage
from psd_tools.constants import Tag

from psd2fusion.parse_psd import parse_psd

REAL_PSD = "D:/Downloads/a.psd"
REAL_SHA256 = "574d8a6511b2aabe744835d81ed76c8fc8ffd0c9c5678f3359e8eda10f9174db"

_ABSENT = object()


def _sha256_of(path):
    with open(path, "rb") as h:
        return hashlib.sha256(h.read()).hexdigest()


def _build_psd(tmpdir, clbl):
    """Build 8x8 flat PSD with 1 base + 1 clipped member, save, return path.

    clbl is _ABSENT, 0, or 1. Tag is set ONLY on the base layer.
    """
    psd = PSDImage.new("RGB", (8, 8), color=0)
    base_img = Image.new("RGBA", (8, 8), (200, 30, 30, 255))
    mem_img = Image.new("RGBA", (8, 8), (30, 200, 30, 255))
    base = psd.create_pixel_layer(base_img, name="p501-base")
    mem = psd.create_pixel_layer(mem_img, name="p501-member")
    mem.clipping = True
    if clbl is not _ABSENT:
        assert clbl in (0, 1)
        base.tagged_blocks.set_data(Tag.BLEND_CLIPPING_ELEMENTS, clbl)
    path = os.path.join(
        tmpdir, "p501_%s.psd" % ("absent" if clbl is _ABSENT else str(clbl))
    )
    psd.save(path)
    return path


def _raw_base_member(path):
    reopened = PSDImage.open(path)
    layers = list(reopened)
    assert len(layers) == 2, [getattr(l, "name", None) for l in layers]
    bases = [l for l in layers if not bool(getattr(l, "clipping", False))]
    mems = [l for l in layers if bool(getattr(l, "clipping", False))]
    assert len(bases) == 1 and len(mems) == 1
    return bases[0], mems[0]


class P501ProvenanceTests(unittest.TestCase):
    def test_absent_is_default_true(self):
        with tempfile.TemporaryDirectory() as d:
            path = _build_psd(d, _ABSENT)
            raw_base, raw_mem = _raw_base_member(path)
            # Byte proof: tag absent after round-trip.
            self.assertFalse(Tag.BLEND_CLIPPING_ELEMENTS in raw_base.tagged_blocks)
            self.assertTrue(bool(raw_mem.clipping))
            doc = parse_psd(path)
            self.assertEqual(1, len(doc.clipping_chains))
            chain = doc.clipping_chains[0]
            self.assertIs(chain.blend_clipped_as_group, True)
            self.assertEqual(
                "photoshop_default_true", chain.blend_clipped_as_group_provenance
            )
            self.assertEqual(1, len(chain.member_ids))
            self.assertEqual(64, len(doc.source_sha256))
            self.assertEqual(doc.source_sha256, _sha256_of(path))

    def test_explicit_true_is_explicit(self):
        with tempfile.TemporaryDirectory() as d:
            path = _build_psd(d, 1)
            raw_base, raw_mem = _raw_base_member(path)
            # Byte proof: tag present with value 1 after round-trip.
            self.assertTrue(Tag.BLEND_CLIPPING_ELEMENTS in raw_base.tagged_blocks)
            self.assertEqual(
                1, int(raw_base.tagged_blocks.get_data(Tag.BLEND_CLIPPING_ELEMENTS))
            )
            self.assertTrue(bool(raw_mem.clipping))
            doc = parse_psd(path)
            self.assertEqual(1, len(doc.clipping_chains))
            chain = doc.clipping_chains[0]
            self.assertIs(chain.blend_clipped_as_group, True)
            self.assertEqual("explicit_psd_clbl", chain.blend_clipped_as_group_provenance)

    def test_explicit_false_is_false_explicit(self):
        with tempfile.TemporaryDirectory() as d:
            path = _build_psd(d, 0)
            raw_base, raw_mem = _raw_base_member(path)
            self.assertTrue(Tag.BLEND_CLIPPING_ELEMENTS in raw_base.tagged_blocks)
            self.assertEqual(
                0, int(raw_base.tagged_blocks.get_data(Tag.BLEND_CLIPPING_ELEMENTS))
            )
            self.assertTrue(bool(raw_mem.clipping))
            doc = parse_psd(path)
            self.assertEqual(1, len(doc.clipping_chains))
            chain = doc.clipping_chains[0]
            self.assertIs(chain.blend_clipped_as_group, False)
            self.assertEqual("explicit_psd_clbl", chain.blend_clipped_as_group_provenance)

    def test_absent_and_explicit_true_provenance_differ(self):
        # No semantic equivalence inferred: same bool, different provenance.
        with tempfile.TemporaryDirectory() as d:
            doc_abs = parse_psd(_build_psd(d, _ABSENT))
            doc_exp = parse_psd(_build_psd(d, 1))
        self.assertEqual(
            doc_abs.clipping_chains[0].blend_clipped_as_group,
            doc_exp.clipping_chains[0].blend_clipped_as_group,
        )
        self.assertNotEqual(
            doc_abs.clipping_chains[0].blend_clipped_as_group_provenance,
            doc_exp.clipping_chains[0].blend_clipped_as_group_provenance,
        )

    @unittest.skipUnless(os.path.isfile(REAL_PSD), "real PSD not mounted")
    def test_real_psd_census_all_default_true(self):
        from psd2fusion.semantic import index_layers

        self.assertEqual(REAL_SHA256, _sha256_of(REAL_PSD))
        doc = parse_psd(REAL_PSD)
        self.assertEqual(REAL_SHA256, doc.source_sha256)
        self.assertEqual(23, len(doc.clipping_chains))
        self.assertEqual(59, sum(len(c.member_ids) for c in doc.clipping_chains))
        for c in doc.clipping_chains:
            self.assertIs(c.blend_clipped_as_group, True)
            self.assertEqual(
                "photoshop_default_true", c.blend_clipped_as_group_provenance
            )
        # Byte proof: zero explicit tags anywhere.
        psd = PSDImage.open(REAL_PSD)
        ds = list(psd.descendants())
        self.assertEqual(136, len(ds))
        self.assertEqual(
            0,
            sum(
                1
                for l in ds
                if getattr(l, "tagged_blocks", None) is not None
                and Tag.BLEND_CLIPPING_ELEMENTS
                in getattr(l, "tagged_blocks", None)
            ),
        )
        idx = index_layers(doc.children)
        self.assertTrue(
            all(idx[c.base_id].parent_id is not None for c in doc.clipping_chains)
        )


if __name__ == "__main__":
    unittest.main()
