"""PARITY-005 P5-05 Axis C: pairwise discrimination matrix referee test (offline).

Replays p504_matrix.json predictions, asserts per-pair best-fixture margins
at EPS=0.01, guards p503-07 degeneracy, and provides the S-NONDISCRIMINATING
report path. Oracle-independent: reads the committed evidence JSON only,
imports no production lowering and no oracle module.
"""
import itertools
import json
import os
import unittest

EPS = 0.01
MATRIX = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    ".control",
    "evidence",
    "PARITY-005",
    "20260905-p504-matrix",
    "p504_matrix.json",
)
# (pair, best_fixture, expected_Linf) from Axis C audit of the evidence JSON.
EXPECTED_BEST = {
    ("H1", "H2"): ("p503-04", 0.162),
    ("H1", "H3"): ("p503-05R", 0.57408),
    ("H1", "H4"): ("p503-04", 0.135),
    ("H1", "H5"): ("p503-03", 0.524),
    ("H2", "H3"): ("p503-05R", 0.57408),
    ("H2", "H4"): ("p503-04", 0.198),
    ("H2", "H5"): ("p503-03", 0.524),
    ("H3", "H4"): ("p503-05R", 0.5568),
    ("H3", "H5"): ("p503-05R", 0.576),
    ("H4", "H5"): ("p503-03", 0.587),
}
REPLAY_TOL = 1e-6  # 6dp rounding replay only; EPS margin is 1e-2.
HIDS = ["H1", "H2", "H3", "H4", "H5"]


def _linf(a, b):
    return max(abs(x - y) for x, y in zip(a, b))


def _load():
    with open(os.path.normpath(MATRIX), "r", encoding="utf-8") as h:
        return json.load(h)


class P505DiscriminationTests(unittest.TestCase):
    def test_every_pair_has_above_noise_discriminator(self):
        doc = _load()
        preds, fids = doc["predictions"], doc["fixture_ids"]
        for (a, b), (bfix, bexp) in EXPECTED_BEST.items():
            row = {f: _linf(preds[f][a], preds[f][b]) for f in fids}
            best = max(row, key=row.get)
            got = row[best]
            self.assertGreaterEqual(
                got, EPS, "S-NONDISCRIMINATING %s-%s best=%r" % (a, b, got)
            )
            self.assertEqual(best, bfix, "%s-%s best %s != %s %r" % (a, b, best, bfix, row))
            self.assertAlmostEqual(got, bexp, delta=REPLAY_TOL)

    def test_universal_fixtures_cover_all_pairs(self):
        doc = _load()
        preds = doc["predictions"]
        pairs = list(itertools.combinations(HIDS, 2))
        for uni in ("p503-04", "p503-06"):
            worst = min(_linf(preds[uni][a], preds[uni][b]) for a, b in pairs)
            self.assertGreaterEqual(worst, EPS, "%s min %r < EPS" % (uni, worst))
        self.assertAlmostEqual(
            min(_linf(preds["p503-04"][a], preds["p503-04"][b]) for a, b in pairs),
            0.111,
            delta=REPLAY_TOL,
        )

    def test_degeneracy_control_never_discriminates(self):
        doc = _load()
        preds = doc["predictions"]
        for a, b in itertools.combinations(HIDS, 2):
            self.assertEqual(_linf(preds["p503-07"][a], preds["p503-07"][b]), 0.0)

    def test_h1_h2_opaque_degeneracy_is_selection_risk(self):
        # H1==H2 on opaque fixtures must not be read as a tie: p503-04 breaks it.
        doc = _load()
        preds = doc["predictions"]
        for f in ("p503-01", "p503-02", "p503-03", "p503-05", "p503-05R", "p503-07"):
            self.assertEqual(_linf(preds[f]["H1"], preds[f]["H2"]), 0.0, f)
        self.assertAlmostEqual(
            _linf(preds["p503-04"]["H1"], preds["p503-04"]["H2"]), 0.162, delta=REPLAY_TOL
        )

    def test_alpha_gap_flagged_for_p511(self):
        # p503-06 exposes RGB but NOT alpha (all A==1.0 on opaque backdrop).
        doc = _load()
        preds = doc["predictions"]
        for h in HIDS:
            self.assertEqual(preds["p503-06"][h][3], 1.0)
        # Only alpha divergence in matrix: p503-02 x H5 (0.05). 06T still required.
        self.assertAlmostEqual(
            abs(preds["p503-02"]["H1"][3] - preds["p503-02"]["H5"][3]),
            0.05,
            delta=REPLAY_TOL,
        )


if __name__ == "__main__":
    unittest.main()
