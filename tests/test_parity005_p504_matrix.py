"""PARITY-005 P5-04 tests: matrix executability, determinism, discrimination."""
import itertools
import os
import sys
import unittest

_HERE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "parity"
)
sys.path.insert(0, os.path.normpath(_HERE))
import p5_03_oracles as O
from p5_04_matrix import FIXTURES, HIDS, build_matrix

EPS = 0.01  # above 8-bit LSB (0.0039) and 1-LSB host noise


class P504MatrixTests(unittest.TestCase):
    def test_all_five_executable_on_all_fixtures(self):
        self.assertEqual(["H1", "H2", "H3", "H4", "H5"], sorted(HIDS))
        for fid, kw in sorted(FIXTURES.items()):
            for hid in HIDS:
                r = O.run_oracle(hid, **kw)
                self.assertEqual(4, len(r))
                self.assertTrue(all(0.0 <= float(v) <= 1.0 for v in r), (hid, fid, r))

    def test_determinism_guard(self):
        self.assertTrue(
            O.determinism_guard({k: dict(v) for k, v in FIXTURES.items()}, repeats=3)
        )
        d1, d2 = build_matrix(), build_matrix()
        self.assertEqual(d1["predictions"], d2["predictions"])

    def test_discriminator_per_live_pair_or_nondiscriminating_report(self):
        doc = build_matrix()
        for x, y in itertools.combinations(sorted(HIDS), 2):
            best_f, best_d = None, -1.0
            for f in doc["fixture_ids"]:
                d = max(
                    abs(a - b)
                    for a, b in zip(doc["predictions"][f][x], doc["predictions"][f][y])
                )
                if d > best_d:
                    best_f, best_d = f, d
            self.assertGreaterEqual(
                best_d,
                EPS,
                "S-NONDISCRIMINATING %s vs %s best=%g on %s" % (x, y, best_d, best_f),
            )
        # p503-07 must be the total-degeneracy control, never a discriminator
        for x, y in itertools.combinations(sorted(HIDS), 2):
            d7 = max(
                abs(a - b)
                for a, b in zip(doc["predictions"]["p503-07"][x], doc["predictions"]["p503-07"][y])
            )
            self.assertEqual(0.0, d7, (x, y))

    def test_no_production_import_in_oracle_path(self):
        # Source-scan only (see scripts/parity/p5_04_matrix.py): the full
        # suite process legitimately imports psd2fusion for other tests.
        for name in ("p5_03_oracles.py", "p5_04_matrix.py"):
            with open(os.path.join(os.path.normpath(_HERE), name), encoding="utf-8") as h:
                for line in h.read().splitlines():
                    stripped = line.strip()
                    self.assertFalse(
                        stripped.startswith("import psd2fusion")
                        or stripped.startswith("from psd2fusion"),
                        (name, stripped),
                    )


if __name__ == "__main__":
    unittest.main()
