"""PARITY-005 P5-17: span termination / no cross-parent membership.

Stage S3 / Axis A. Structural only. No Fusion/pixel truth.
Proves parse_psd.attach_clipping invariants executably:
  same-parent (zip per level), contiguous (unclipped terminates),
  orphan diagnosed, recursion per group (cross-group impossible).
"""
import os
import unittest

from PIL import Image
from psd_tools import PSDImage

from psd2fusion.parse_psd import parse_psd
from psd2fusion.semantic import (
    ClippingChain,
    SemanticDocument,
    SemanticGroup,
    SemanticLayer,
    index_layers,
)

REAL_PSD = "D:/Downloads/a.psd"
REAL_SHA256 = "574d8a6511b2aabe744835d81ed76c8fc8ffd0c9c5678f3359e8eda10f9174db"


def _assert_same_parent_contiguous(doc):
    """Local executable invariant: every chain is one same-parent contiguous span."""
    idx = index_layers(doc.children)
    by_parent = {}
    for layer in idx.values():
        by_parent.setdefault(layer.parent_id, []).append(layer)
    for layers in by_parent.values():
        layers.sort(key=lambda l: l.sibling_index)
    for chain in doc.clipping_chains:
        assert chain.base_id in idx, "missing base %s" % chain.base_id
        base = idx[chain.base_id]
        members = [idx[mid] for mid in chain.member_ids]
        assert members, "empty chain for base %s" % chain.base_id
        for m in members:
            assert m.parent_id == base.parent_id, (
                "cross-parent span rejected: base %s parent %r != member %s parent %r"
                % (base.id, base.parent_id, m.id, m.parent_id)
            )
            assert m.clipping_base_id == base.id, "member backpointer %s" % m.id
            assert m.id in base.clipping_members, "base forward pointer %s" % m.id
        sibs = by_parent[base.parent_id]
        pos = {l.id: i for i, l in enumerate(sibs)}
        assert pos[base.id] < min(pos[m.id] for m in members), "base must precede members"
        span = sibs[pos[base.id] + 1 : pos[base.id] + 1 + len(members)]
        assert [l.id for l in span] == chain.member_ids, (
            "noncontiguous span for base %s: expected %r got %r"
            % (base.id, chain.member_ids, [l.id for l in span])
        )
    for layer in idx.values():
        if (
            layer.clipping_base_id is None
            and layer.id not in {c.base_id for c in doc.clipping_chains}
        ):
            chained = any(layer.id in c.member_ids for c in doc.clipping_chains)
            assert not chained, "orphan %s must not appear in any chain" % layer.id
    return True


def _build_flat(tmpdir, flags, name="p517"):
    """Build 8x8 PSD; flags[i]=True means layer i clipped (bottom-to-top order)."""
    import os as _os

    psd = PSDImage.new("RGB", (8, 8), color=0)
    for i, clipped in enumerate(flags):
        img = Image.new("RGBA", (8, 8), (20 * i % 255, 100, 200, 255))
        layer = psd.create_pixel_layer(img, name="%s-%d" % (name, i))
        layer.clipping = bool(clipped)
    path = _os.path.join(
        tmpdir, "%s_%s.psd" % (name, "".join("1" if f else "0" for f in flags))
    )
    psd.save(path)
    return path


def _doc_of(children, chains=()):
    return SemanticDocument(
        source_path="p517-fixture.psd",
        source_sha256="0" * 64,
        parser="fixture",
        parser_version="1",
        width=8,
        height=8,
        children=list(children),
        clipping_chains=list(chains),
    )


class P517SyntheticSpanTests(unittest.TestCase):
    def test_interrupted_chain_splits_into_two(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            doc = parse_psd(_build_flat(d, [False, True, False, True], name="split"))
        self.assertEqual(2, len(doc.clipping_chains))
        self.assertEqual(1, len(doc.clipping_chains[0].member_ids))
        self.assertEqual(1, len(doc.clipping_chains[1].member_ids))
        self.assertTrue(_assert_same_parent_contiguous(doc))

    def test_orphan_first_child_diagnosed_no_chain(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            doc = parse_psd(_build_flat(d, [True, False, True], name="orphan"))
        self.assertEqual(1, len(doc.clipping_chains))
        idx = index_layers(doc.children)
        orphans = [
            l for l in idx.values() if l.sibling_index == 0 and l.parent_id is None
        ]
        self.assertTrue(
            any("Orphan clipping flag" in w for l in orphans for w in l.warnings)
        )
        self.assertTrue(any("orphan clipping flag" in w for w in doc.warnings))
        self.assertTrue(_assert_same_parent_contiguous(doc))

    def test_chain_at_end_flushed_lone_base_makes_no_chain(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            doc = parse_psd(_build_flat(d, [False, True, True], name="end"))
            doc2 = parse_psd(_build_flat(d, [False], name="lone"))
        self.assertEqual(1, len(doc.clipping_chains))
        self.assertEqual(2, len(doc.clipping_chains[0].member_ids))
        self.assertEqual(0, len(doc2.clipping_chains))
        self.assertTrue(_assert_same_parent_contiguous(doc))


class P517GroupBoundaryTests(unittest.TestCase):
    def test_cross_group_members_never_merge(self):
        g1 = SemanticGroup(id="g1", name="G1", parent_id=None, sibling_index=0, raw_index=0)
        g2 = SemanticGroup(id="g2", name="G2", parent_id=None, sibling_index=1, raw_index=1)
        b1 = SemanticLayer(id="b1", name="b1", parent_id="g1", sibling_index=0, raw_index=0)
        m1 = SemanticLayer(
            id="m1", name="m1", parent_id="g1", sibling_index=1, raw_index=1,
            clipping_base_id="b1",
        )
        b1.clipping_members = ["m1"]
        b2 = SemanticLayer(id="b2", name="b2", parent_id="g2", sibling_index=0, raw_index=0)
        m2 = SemanticLayer(
            id="m2", name="m2", parent_id="g2", sibling_index=1, raw_index=1,
            clipping_base_id="b2",
        )
        b2.clipping_members = ["m2"]
        g1.children = [b1, m1]
        g2.children = [b2, m2]
        doc = _doc_of(
            [g1, g2],
            [
                ClippingChain(base_id="b1", member_ids=["m1"]),
                ClippingChain(base_id="b2", member_ids=["m2"]),
            ],
        )
        self.assertTrue(_assert_same_parent_contiguous(doc))
        bad = _doc_of([g1, g2], [ClippingChain(base_id="b1", member_ids=["m1", "m2"])])
        with self.assertRaisesRegex(AssertionError, "cross-parent"):
            _assert_same_parent_contiguous(bad)

    def test_root_vs_nested_sibling_index_independent(self):
        b_root = SemanticLayer(id="br", name="br", parent_id=None, sibling_index=0, raw_index=0)
        u_root = SemanticLayer(id="ur", name="ur", parent_id=None, sibling_index=1, raw_index=1)
        g = SemanticGroup(id="g", name="G", parent_id=None, sibling_index=2, raw_index=2)
        b_g = SemanticLayer(id="bg", name="bg", parent_id="g", sibling_index=0, raw_index=0)
        m_g = SemanticLayer(
            id="mg", name="mg", parent_id="g", sibling_index=1, raw_index=1,
            clipping_base_id="bg",
        )
        b_g.clipping_members = ["mg"]
        g.children = [b_g, m_g]
        doc = _doc_of(
            [b_root, u_root, g], [ClippingChain(base_id="bg", member_ids=["mg"])]
        )
        self.assertTrue(_assert_same_parent_contiguous(doc))
        bad = _doc_of(
            [b_root, u_root, g], [ClippingChain(base_id="br", member_ids=["mg"])]
        )
        with self.assertRaisesRegex(AssertionError, "cross-parent"):
            _assert_same_parent_contiguous(bad)

    def test_noncontiguous_chain_rejected(self):
        b = SemanticLayer(
            id="b", name="b", parent_id=None, sibling_index=0, raw_index=0,
            clipping_members=["m1", "m2"],
        )
        m1 = SemanticLayer(
            id="m1", name="m1", parent_id=None, sibling_index=1, raw_index=1,
            clipping_base_id="b",
        )
        u = SemanticLayer(id="u", name="u", parent_id=None, sibling_index=2, raw_index=2)
        m2 = SemanticLayer(
            id="m2", name="m2", parent_id=None, sibling_index=3, raw_index=3,
            clipping_base_id="b",
        )
        doc = _doc_of(
            [b, m1, u, m2], [ClippingChain(base_id="b", member_ids=["m1", "m2"])]
        )
        with self.assertRaisesRegex(AssertionError, "noncontiguous"):
            _assert_same_parent_contiguous(doc)


class P517RealPSDContiguityTests(unittest.TestCase):
    @unittest.skipUnless(os.path.isfile(REAL_PSD), "real PSD not mounted")
    def test_real_psd_23_chain_contiguity_spot_check(self):
        import hashlib

        with open(REAL_PSD, "rb") as h:
            self.assertEqual(REAL_SHA256, hashlib.sha256(h.read()).hexdigest())
        doc = parse_psd(REAL_PSD)
        self.assertEqual(23, len(doc.clipping_chains))
        self.assertEqual(59, sum(len(c.member_ids) for c in doc.clipping_chains))
        self.assertTrue(_assert_same_parent_contiguous(doc))
        idx = index_layers(doc.children)
        self.assertTrue(
            all(idx[c.base_id].parent_id is not None for c in doc.clipping_chains)
        )


if __name__ == "__main__":
    unittest.main()
